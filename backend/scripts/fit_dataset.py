from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.model import fit_normal_bank


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit the OpenCV normal bank from a prepared dataset's train/good images only.")
    parser.add_argument("--dataset-dir", required=True, type=Path, help="Prepared dataset root with <class>/train/good")
    parser.add_argument("--class-name", required=True, help="Dataset category, for example bottle, pcb1, or candle")
    parser.add_argument("--dataset-id", choices=("MVTec-AD-v1", "VisA-1cls"), default="MVTec-AD-v1")
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--model-dir", type=Path, default=None)
    args = parser.parse_args()
    category = args.dataset_dir / args.class_name
    if not category.is_dir():
        raise SystemExit(f"Category folder not found: {category}")
    if args.dataset_id == "VisA-1cls":
        manifest_path = category / "dataset_manifest.json"
        if not manifest_path.is_file():
            raise SystemExit("VisA requires the provenance manifest produced by backend/scripts/prepare_visa.py.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("dataset") != "Visual Anomaly (VisA), 2022-09-22 release" or manifest.get("class_name") != args.class_name:
            raise SystemExit("The prepared dataset manifest does not match the requested VisA category.")
    paths = sorted(p for p in (category / "train" / "good").glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"})
    if len(paths) < 8:
        raise SystemExit(f"Need at least 8 normal train/good images for a disjoint fit/calibration split; found {len(paths)}.")
    random.Random(args.seed).shuffle(paths)
    calibration_count = max(4, round(len(paths) * 0.2))
    calibration, training = paths[:calibration_count], paths[calibration_count:]
    default_prefix = "mvtec" if args.dataset_id == "MVTec-AD-v1" else "visa"
    default_name = f"{default_prefix}_{args.class_name}"
    model_dir = args.model_dir or (ROOT / "data" / "models" / default_name)
    metadata = fit_normal_bank(training, calibration, model_dir, seed=args.seed, source=f"{args.dataset_id}:{args.class_name}")
    if args.dataset_id == "VisA-1cls":
        manifest_path = category / "dataset_manifest.json"
        metadata["dataset_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        (model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Fitted from {metadata['training_count']} {args.dataset_id} train/good images; calibrated from {metadata['calibration_count']} disjoint train/good images.")
    print("No test images, defect labels, or masks were read during fitting.")
    print(f"Frozen image threshold={metadata['image_threshold']:.6f}; model={model_dir}")


if __name__ == "__main__":
    main()
