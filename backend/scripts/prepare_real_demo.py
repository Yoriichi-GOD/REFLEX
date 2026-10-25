"""Bundle six attributed real photographs and the frozen normal-only models.

Ground-truth masks and expected decisions remain outside the runtime bundle.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import shutil

from app.core.patch_memory import digest, WEIGHTS_SHA256, FEATURE_GRAPH_SHA256

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT.parent / "reflex-data"
BENCH = ROOT / "reports" / "improvement_20261024"
ATTRIBUTION = {"dataset": "VisA", "credit": "Amazon Science; Zou et al., ECCV 2022",
               "source": "https://github.com/amazon-science/spot-diff", "license": "CC BY 4.0",
               "license_url": "https://creativecommons.org/licenses/by/4.0/", "changes": "Original JPEG bytes preserved; model evidence computed live."}


def main():
    target = ROOT / "demo" / "real"
    target.mkdir(parents=True, exist_ok=True)
    cases, audit = [], []
    titles = {"candle": ["Four-candle layout", "Candle edge detail", "Small rim detail"],
              "cashew": ["Cashew surface", "Cashew shape detail", "Subtle surface detail"]}
    for category in ("candle", "cashew"):
        with (BENCH / category / "per_case.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        good = min((r for r in rows if r["label"] == "0"), key=lambda r: float(r["score"]))
        defects = sorted((r for r in rows if r["label"] == "1"), key=lambda r: float(r["score"]))
        for index, row in enumerate((good, defects[-1], defects[0])):
            name = f"{category}-{index+1}.jpg"
            source = DATA / "visa" / "prepared" / category / "test" / row["case_id"]
            # Prepared folders use 'bad'/'good', as in the case identifier.
            assert digest(source) == row["image_sha256"]
            shutil.copyfile(source, target / name)
            cases.append({"id": f"visa-{category}-{index+1}", "category": category,
                          "title": titles[category][index], "description": "Real VisA photograph · analyze live",
                          "image_url": f"/demo/real/{name}", "sha256": digest(source),
                          "synthetic": False, "attribution": ATTRIBUTION})
            audit.append({"demo_id": cases[-1]["id"], "category": category, "case_id": row["case_id"],
                          "image_sha256": digest(source), "offline_score": float(row["score"]),
                          "label_evaluator_only": int(row["label"]), "offline_prediction": int(row["prediction"])})
        model_target = ROOT / "demo" / "profiles" / category
        model_target.mkdir(parents=True, exist_ok=True)
        for filename in ("patch_bank.npz", "metadata.json"):
            shutil.copyfile(BENCH / "models" / category / filename, model_target / filename)
        eval_target = ROOT / "demo" / "evaluations"
        eval_target.mkdir(exist_ok=True)
        shutil.copyfile(BENCH / category / "metrics.json", eval_target / f"{category}.json")
    pretrained = ROOT / "demo" / "pretrained"
    pretrained.mkdir(exist_ok=True)
    for filename, expected in (("resnet50-v1-12.onnx", WEIGHTS_SHA256), ("resnet50-v1-12.features.onnx", FEATURE_GRAPH_SHA256)):
        source = DATA / "models" / filename
        assert digest(source) == expected
        destination = pretrained / filename
        if not destination.exists() or digest(destination) != expected:
            shutil.copyfile(source, destination)
    (target / "cases.json").write_text(json.dumps({"cases": cases, "attribution": ATTRIBUTION,
        "selection": "Curated normal, conspicuous and subtle examples; not an accuracy estimate. No expected decisions or masks supplied to inference."}, indent=2), encoding="utf-8")
    (target / "ATTRIBUTION.md").write_text("# VisA real-image demo\n\nAmazon Science; Zou et al., SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation, ECCV 2022.\n\nSource: https://github.com/amazon-science/spot-diff\n\nLicense: CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/\n\nOriginal JPEG bytes are preserved. Heatmaps and overlays are generated live by REFLEX. Examples are curated illustrations and include a subtle case the current model misses. No mask or expected decision is supplied to the model.\n", encoding="utf-8")
    report = ROOT / "reports" / "real_demo_20261024"
    report.mkdir(parents=True, exist_ok=True)
    (report / "fixture_audit.json").write_text(json.dumps({"count": len(cases), "cases": audit,
         "raw_ground_truth_masks_packaged": False, "training_changes": False}, indent=2), encoding="utf-8")
    print(json.dumps({"real_images": len(cases), "profiles": ["candle", "cashew"], "masks_packaged": False}))


if __name__ == "__main__":
    main()
