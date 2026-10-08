"""Publish the model repo and the Space to Hugging Face.

    pip install huggingface_hub xgboost
    hf auth login                      # a token with write access
    python huggingface/publish.py [--owner ElDoctor]

Regenerate reference.json first (backend/scripts/export_reference_model.py)
when the corpus changes. Daniel Duque's model is converted from the pickle in
Models/ to XGBoost's native format on the way out: Hugging Face flags pickles
as unsafe to load, and the native file needs no Python object to read.
"""

import argparse
import json
import pickle
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "model"
SPACE_DIR = ROOT / "space"
PICKLE = ROOT.parent / "Models" / "modelxgboost.pkl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="ElDoctor")
    args = parser.parse_args()
    api = HfApi()
    model_repo = f"{args.owner}/contractor-ai-latam"
    space_repo = f"{args.owner}/contractor-ai-analizador"

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "model"
        shutil.copytree(MODEL_DIR, staged, ignore=shutil.ignore_patterns("__pycache__"))
        booster = pickle.loads(PICKLE.read_bytes())  # our own file, committed in Models/
        booster.save_model(staged / "bert-xgboost" / "model.ubj")
        (staged / "bert-xgboost" / "feature_names.json").write_text(
            json.dumps(booster.feature_names, ensure_ascii=False, indent=0), encoding="utf-8"
        )
        api.create_repo(model_repo, repo_type="model", exist_ok=True)
        api.upload_folder(repo_id=model_repo, folder_path=staged, commit_message="Publish Contractor AI models")

        space = Path(tmp) / "space"
        shutil.copytree(SPACE_DIR, space, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(MODEL_DIR / "reference.json", space)
        # A static Space: the analyzer runs in the visitor's browser. Gradio
        # Spaces need a paid plan on Hugging Face; static ones are free.
        api.create_repo(space_repo, repo_type="space", space_sdk="static", exist_ok=True)
        api.upload_folder(repo_id=space_repo, repo_type="space", folder_path=space, commit_message="Publish analyzer")

    print(f"https://huggingface.co/{model_repo}")
    print(f"https://huggingface.co/spaces/{space_repo}")


if __name__ == "__main__":
    main()
