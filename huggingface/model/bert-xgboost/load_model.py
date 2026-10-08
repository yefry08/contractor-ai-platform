"""Load Daniel Duque Lozano's base model and inspect it.

    pip install xgboost
    python load_model.py

The booster expects 1554 columns in the order of feature_names.json: 1500
text features from the fine-tuned BERT head (columns "0".."1499"), then 54
one-hot OCDS columns such as "compiledRelease/tender/awardCriteria_priceOnly".
The BERT head's weights are not published, so this script builds a row from
the OCDS columns only and leaves the text features at zero -- enough to see
the model run, not a meaningful prediction.
"""

import json
from pathlib import Path

import xgboost as xgb

HERE = Path(__file__).resolve().parent

booster = xgb.Booster()
booster.load_model(HERE / "model.ubj")
features = json.loads((HERE / "feature_names.json").read_text(encoding="utf-8"))
print(f"{booster.num_boosted_rounds()} trees, {len(features)} features")
print("OCDS columns:", *[f for f in features if not f.isdigit()], sep="\n  ")

row = {f: 0.0 for f in features}
row["compiledRelease/tender/mainProcurementCategory_services"] = 1.0
row["compiledRelease/tender/awardCriteria_priceOnly"] = 1.0
row["compiledRelease/planning/budget/amount/currency_PYG"] = 1.0
matrix = xgb.DMatrix([[row[f] for f in features]], feature_names=features)
print("prediction with empty text features (USD millions):", float(booster.predict(matrix)[0]))
