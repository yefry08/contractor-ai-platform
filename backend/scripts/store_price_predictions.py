"""Store the text-to-price models' predictions and flag what they find.

Reads models/price/oof_predictions.csv and metrics.json from
train_price_models.py. Each stored prediction is the out-of-fold one: it
comes from a model that never saw that contract or any other with the same
wording, so the gap between price and prediction is an honest one.

Only countries whose model beats the statistical layer's own reference
(buyer / category / country median) by at least MIN_ERROR_REDUCTION are
stored -- a model that doesn't do better than a median adds noise, not a
second opinion. Contracts that already carry Daniel Duque's BERT + XGBoost
prediction (Paraguay and the Colombian bulk dataset) are left alone.

Flagging: the original model flagged a contract at twice its prediction,
which fits a model with R2 ~0.7. These models are typically off by x3, so
that rule would flag a third of every country. Instead the residual
log(amount) - log(prediction) gets the same robust test as the statistical
layer: modified z-score against the country's own residuals (median + MAD),
flagged when |z| > 3.5. In practice that means hundreds of times the
prediction, i.e. only the clear cases.

Idempotent: rows written by a previous run of this script are removed first.

    cd backend
    python scripts/store_price_predictions.py            # dry run: prints what it would write
    python scripts/store_price_predictions.py --write
"""

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, update  # noqa: E402

from app import models  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.stats import ZSCORE_THRESHOLD, modified_zscore  # noqa: E402

MODELS = Path(__file__).resolve().parents[1] / "models" / "price"
MODEL_PREFIX = "text-price-"
MIN_ERROR_REDUCTION = 0.10
ORIGINAL_MODEL = "bert-multilingual-xgboost"


def main(write: bool) -> None:
    report = json.loads((MODELS / "metrics.json").read_text(encoding="utf-8"))
    useful = {
        code: r
        for code, r in report.items()
        if r.get("best") and r["error_reduction_vs_reference"] >= MIN_ERROR_REDUCTION
        and r["scores"][r["best"]]["r2_log"] > r["scores"]["reference"]["r2_log"]
    }
    skipped = sorted(set(report) - set(useful))
    print("countries stored:", ", ".join(sorted(useful)), "| skipped:", ", ".join(skipped) or "none")

    rows = defaultdict(list)
    with open(MODELS / "oof_predictions.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["country"] in useful:
                rows[r["country"]].append(r)

    db = SessionLocal()
    try:
        has_original = set(
            db.scalars(select(models.Prediction.contract_id).where(models.Prediction.model_name == ORIGINAL_MODEL))
        )
        plan = []  # (country, contract_id, amount, predicted, perc_error, z)
        summary = {}
        for code, items in rows.items():
            # The residual spread is the country's, measured on every contract;
            # only the writing skips those that already carry the original model.
            resid = [math.log(float(r["amount"])) - math.log(float(r["predicted"])) for r in items]
            med = statistics.median(resid)
            mad = statistics.median(abs(x - med) for x in resid)
            pairs = [(r, e) for r, e in zip(items, resid) if r["contract_id"] not in has_original]
            items = [r for r, _ in pairs]
            flagged = 0
            for r, e in pairs:
                z = modified_zscore(e, med, mad)
                amount, predicted = float(r["amount"]), float(r["predicted"])
                plan.append((code, r["contract_id"], amount, predicted, (amount - predicted) / predicted, z))
                flagged += abs(z) > ZSCORE_THRESHOLD
            summary[code] = {"predictions": len(items), "flagged": flagged, "rate": round(flagged / max(1, len(items)), 4)}
        print(json.dumps(summary, indent=1))
        if not write:
            print("dry run: nothing written (pass --write)")
            return

        # Undo a previous run: our predictions, our NLP-only anomalies, our NLP
        # component on anomalies the statistical layer also raised.
        ours = select(models.Prediction.contract_id).where(models.Prediction.model_name.like(MODEL_PREFIX + "%"))
        db.execute(
            delete(models.Anomaly).where(
                models.Anomaly.contract_id.in_(ours), models.Anomaly.stat_component.is_(None)
            )
        )
        db.execute(update(models.Anomaly).where(models.Anomaly.contract_id.in_(ours)).values(nlp_component=None))
        db.execute(delete(models.Prediction).where(models.Prediction.model_name.like(MODEL_PREFIX + "%")))
        db.commit()

        existing = {
            a.contract_id: a
            for a in db.scalars(select(models.Anomaly).where(models.Anomaly.status == "open"))
        }
        version = date.today().strftime("%Y-%m")
        for i, (code, contract_id, amount, predicted, perc, z) in enumerate(plan, 1):
            db.add(
                models.Prediction(
                    contract_id=contract_id,
                    model_name=MODEL_PREFIX + report[code]["best"],
                    model_version=version,
                    predicted_value_original=predicted,
                )
            )
            if abs(z) > ZSCORE_THRESHOLD:
                anomaly = existing.get(contract_id)
                if anomaly:
                    anomaly.nlp_component = perc  # the statistical layer saw it too
                else:
                    db.add(
                        models.Anomaly(
                            contract_id=contract_id,
                            anomaly_type="overcost" if z > 0 else "undercost",
                            composite_score=abs(z),
                            nlp_component=perc,
                            stat_component=None,
                            status="open",
                        )
                    )
            if i % 2000 == 0:
                db.commit()
                print(f"  ... {i} predictions")
        db.commit()
        print("written")
    finally:
        db.close()


if __name__ == "__main__":
    main("--write" in sys.argv)
