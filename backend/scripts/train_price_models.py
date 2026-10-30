"""Train a text-to-price model for every country and measure it honestly.

The original model (Daniel Duque's BERT + XGBoost) only covers Paraguay and
part of Colombia, and its fine-tuned BERT head isn't in the repo, so it can't
be retrained here. This script trains, per country, a model that reads what
the contract says it buys (title + description) plus its category,
procurement method and buyer, and predicts log(amount) in the country's main
currency -- the same job, with features a CPU can afford:

  - TF-IDF over words (1-2 grams) and characters (3-5 grams), one-hot
    category / method / buyer;
  - multilingual sentence embeddings (paraphrase-multilingual-MiniLM-L12-v2,
    mean-pooled, run once on CPU and cached), which carry meaning across
    wordings: "tóner" and "cartuchos de tinta" land close together;
  - five learners compared on the same folds: ridge on TF-IDF, XGBoost on a
    compact TF-IDF, ridge and XGBoost on the embeddings, and ridge on TF-IDF
    plus embeddings.

Evaluation is out-of-fold with GroupKFold grouped by normalized text, so a
contract is never predicted by a model that saw a contract with the same
wording (Costa Rica, for one, repeats titles: 1,033 distinct in 5,297). Every
model is compared against the statistical layer's own reference -- the median
of the same buyer, else category, else country, computed on the training
fold -- because a model that doesn't beat that median adds nothing.

    cd backend
    pip install -r requirements-train.txt
    python scripts/train_price_models.py --embed-only   # once: cache the embeddings
    python scripts/train_price_models.py

Writes models/price/<COUNTRY>.joblib (final model fit on all rows),
models/price/metrics.json and models/price/oof_predictions.csv (one
out-of-fold prediction per contract). It does not touch the database.
"""

import csv
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import engine  # noqa: E402
from app.stats import MIN_GROUP_SIZE  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "models" / "price"
MIN_ROWS = 300  # below this, five folds leave too few contracts to learn wording
FOLDS = 5
ENCODER = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMB_CACHE = OUT / "embeddings.npz"
EMB_WEIGHT = 2.0  # TF-IDF rows and embeddings are both unit-norm; this lets the ridge lean on meaning
ID_LIKE = re.compile(r"^[\w/.\-]*\d[\w/.\-]*$")  # "R/212040370018", "LP-ABR-1-2026-GRA"


def contract_text(title: str | None, description: str | None) -> str:
    parts = []
    for p in (title, description):
        p = (p or "").strip()
        if not p or ID_LIKE.match(p):
            continue  # Uruguay's and Peru's titles are process codes, not words
        if parts and (p.lower().startswith(parts[0].lower()[:40]) or parts[0].lower().startswith(p.lower()[:40])):
            continue  # description repeating the title adds nothing
        parts.append(p)
    return " | ".join(parts).lower()


def load():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select id, country_code, currency, title, description, category_code, procurement_method, buyer_id, "
                "amount_original from contracts where amount_original > 0 and currency is not null"
            )
        ).all()
    by_country = defaultdict(list)
    for r in rows:
        by_country[r.country_code].append(r)
    return by_country


def embed(ids, texts):
    """Unit-norm, mean-pooled sentence embeddings, cached by contract id."""
    cache = {}
    if EMB_CACHE.exists():
        z = np.load(EMB_CACHE, allow_pickle=False)
        cache = dict(zip(z["ids"].tolist(), z["emb"]))
    missing = [(i, t) for i, t in zip(ids, texts) if i not in cache]
    if missing:
        import torch
        from transformers import AutoModel, AutoTokenizer

        def save():
            keys = list(cache)
            np.savez(EMB_CACHE, ids=np.array(keys), emb=np.stack([cache[k] for k in keys]))

        # Each distinct text once, shortest first: a batch pads to its longest
        # text, and mixing Colombia's 200-character objects with 14-character
        # Uruguayan items ran at ~5 texts/s on CPU.
        by_text = defaultdict(list)
        for i, t in missing:
            by_text[t].append(i)
        unique = sorted(by_text, key=len)
        tok = AutoTokenizer.from_pretrained(ENCODER)
        model = AutoModel.from_pretrained(ENCODER).eval()
        with torch.inference_mode():
            for start in range(0, len(unique), 64):
                batch = unique[start : start + 64]
                enc = tok(batch, padding=True, truncation=True, max_length=64, return_tensors="pt")
                out = model(**enc).last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1)
                vec = torch.nn.functional.normalize((out * mask).sum(1) / mask.sum(1), dim=1).numpy()
                for t, v in zip(batch, vec):
                    for i in by_text[t]:
                        cache[i] = v
                if (start // 64) % 50 == 0:
                    log(f"  embeddings {start + len(batch)}/{len(unique)} distinct texts")
                if (start // 64) % 150 == 149:
                    save()  # a cut-off run resumes from here
        save()
    return np.stack([cache[i] for i in ids]).astype(np.float32)


class Features:
    """`full` (words + character n-grams + categories) feeds the ridge. Trees
    get `compact` (the 4,000 most frequent words + categories): on the full
    ~25,000 sparse columns XGBoost took ~110 s per fold for 3,000 contracts."""

    def __init__(self, kind: str = "full"):
        self.kind = kind
        compact = kind == "compact"
        self.words = None if kind == "emb" else TfidfVectorizer(
            ngram_range=(1, 1) if compact else (1, 2), min_df=3 if compact else 2,
            max_features=4_000 if compact else 40_000, sublinear_tf=True,
        )
        self.chars = None if kind in ("compact", "emb") else TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=40_000, sublinear_tf=True
        )
        self.cats = OneHotEncoder(handle_unknown="ignore", min_frequency=3)

    @staticmethod
    def _cat(rows):
        return [[r.category_code or "-", r.procurement_method or "-", r.buyer_id or "-"] for r in rows]

    def _build(self, rows, texts, emb, fit):
        def apply(v, x):
            return v.fit_transform(x) if fit else v.transform(x)

        parts = [apply(v, texts) for v in (self.words, self.chars) if v is not None]
        if self.kind in ("emb", "hybrid"):
            parts.append(sparse.csr_matrix(emb * (EMB_WEIGHT if self.kind == "hybrid" else 1.0)))
        parts.append(apply(self.cats, self._cat(rows)))
        return sparse.hstack(parts).tocsr()

    def fit_transform(self, rows, texts, emb=None):
        return self._build(rows, texts, emb, fit=True)

    def transform(self, rows, texts, emb=None):
        return self._build(rows, texts, emb, fit=False)


FEATURES_FOR = {"ridge": "full", "xgboost": "compact", "emb_ridge": "emb", "emb_xgb": "emb", "hybrid": "hybrid"}
LEARNERS = list(FEATURES_FOR)


def make_model(kind: str):
    if kind in ("ridge", "hybrid"):
        return Ridge(alpha=3.0)
    if kind == "emb_ridge":
        return Ridge(alpha=1.0)
    # Imported here, not at the top: torch (embeddings) and xgboost each bring
    # their own OpenMP runtime, and loaded in one process on Windows they fight
    # over threads -- embedding ran ~10x slower. Run --embed-only first.
    from xgboost import XGBRegressor

    return XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.06,
        subsample=0.8,
        colsample_bytree=0.4,
        min_child_weight=3,
        tree_method="hist",
        n_jobs=4,
        verbosity=0,
    )


def reference_median(train_rows, y_train, rows):
    """The statistical layer's reference: buyer median if the buyer has enough
    contracts, else category, else country -- fitted on the training fold."""
    by_buyer, by_cat = defaultdict(list), defaultdict(list)
    for r, y in zip(train_rows, y_train):
        if r.buyer_id:
            by_buyer[r.buyer_id].append(y)
        if r.category_code:
            by_cat[r.category_code].append(y)
    country = float(np.median(y_train))
    med_buyer = {k: float(np.median(v)) for k, v in by_buyer.items() if len(v) >= MIN_GROUP_SIZE}
    med_cat = {k: float(np.median(v)) for k, v in by_cat.items() if len(v) >= MIN_GROUP_SIZE}
    return np.array([med_buyer.get(r.buyer_id, med_cat.get(r.category_code, country)) for r in rows])


def metrics(y, pred):
    err = np.abs(y - pred)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "r2_log": round(1 - ss_res / ss_tot, 3) if ss_tot else 0.0,
        "median_factor": round(float(math.exp(np.median(err))), 2),  # typical "off by ×N"
        "within_2x": round(float(np.mean(err <= math.log(2))), 3),
    }


def train_country(code, rows):
    currency = Counter(r.currency for r in rows).most_common(1)[0][0]
    rows = [r for r in rows if r.currency == currency]
    texts = [contract_text(r.title, r.description) for r in rows]
    keep = [i for i, t in enumerate(texts) if t]
    rows, texts = [rows[i] for i in keep], [texts[i] for i in keep]
    y = np.log(np.array([r.amount_original for r in rows], dtype=float))
    result = {"currency": currency, "rows": len(rows), "distinct_texts": len(set(texts))}
    if len(rows) < MIN_ROWS:
        result["status"] = "insufficient"
        return result, None, None

    groups = np.array([hash(t) for t in texts])
    emb = embed([r.id for r in rows], texts)
    oof = {k: np.zeros(len(rows)) for k in ("reference", *LEARNERS)}
    for fold, (train_idx, test_idx) in enumerate(GroupKFold(n_splits=FOLDS).split(texts, y, groups), 1):
        t0 = time.time()
        tr_rows = [rows[i] for i in train_idx]
        te_rows = [rows[i] for i in test_idx]
        oof["reference"][test_idx] = reference_median(tr_rows, y[train_idx], te_rows)
        times = []
        for kind in LEARNERS:
            feats = Features(FEATURES_FOR[kind])
            x_tr = feats.fit_transform(tr_rows, [texts[i] for i in train_idx], emb[train_idx])
            x_te = feats.transform(te_rows, [texts[i] for i in test_idx], emb[test_idx])
            model = make_model(kind).fit(x_tr, y[train_idx])
            oof[kind][test_idx] = model.predict(x_te)
            times.append(f"{kind} {time.time() - t0:.0f}s/{x_tr.shape[1]} cols")
            t0 = time.time()
        log(f"  {code} fold {fold}/{FOLDS}: " + ", ".join(times))

    scores = {k: metrics(y, v) for k, v in oof.items()}
    best = min(LEARNERS, key=lambda k: np.median(np.abs(y - oof[k])))
    ref_err = float(np.median(np.abs(y - oof["reference"])))
    best_err = float(np.median(np.abs(y - oof[best])))
    result.update(
        {
            "scores": scores,
            "best": best,
            # Share of the reference's typical error the model removes.
            "error_reduction_vs_reference": round(1 - best_err / ref_err, 3) if ref_err else 0.0,
        }
    )

    feats = Features(FEATURES_FOR[best])
    final = make_model(best).fit(feats.fit_transform(rows, texts, emb), y)
    oof_rows = [(r.id, code, currency, float(math.exp(y[i])), float(math.exp(oof[best][i]))) for i, r in enumerate(rows)]
    bundle = {"features": feats, "model": final, "currency": currency, "kind": best}
    if FEATURES_FOR[best] in ("emb", "hybrid"):
        bundle["encoder"] = ENCODER  # predicting needs the same embeddings
    return result, bundle, oof_rows


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    embed_only = "--embed-only" in sys.argv
    only = {a for a in sys.argv[1:] if not a.startswith("--")}  # optional country codes, e.g. BR CL
    started = time.time()
    data = load()
    log(f"loaded {sum(len(v) for v in data.values())} contracts in {time.time() - started:.0f}s")
    if only:
        data = {k: v for k, v in data.items() if k in only}
    if embed_only:
        rows = [r for v in data.values() for r in v]
        texts = [contract_text(r.title, r.description) for r in rows]
        keep = [(r.id, t) for r, t in zip(rows, texts) if t]
        embed([i for i, _ in keep], [t for _, t in keep])
        log(f"embeddings cached for {len(keep)} contracts")
        return
    report, all_oof = {}, []
    for code in sorted(data):
        started = time.time()
        result, bundle, oof_rows = train_country(code, data[code])
        result["seconds"] = round(time.time() - started)
        report[code] = result
        if bundle:
            joblib.dump(bundle, OUT / f"{code}.joblib", compress=3)
            all_oof.extend(oof_rows)
        print(code, json.dumps(result, ensure_ascii=False), flush=True)

    if only:
        return  # partial runs don't overwrite the full report
    (OUT / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT / "oof_predictions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["contract_id", "country", "currency", "amount", "predicted"])
        w.writerows(all_oof)


if __name__ == "__main__":
    main()
