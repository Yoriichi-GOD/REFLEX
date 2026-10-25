"""Integrity and split audit for the supplied synthetic kit and local VisA subset."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import zipfile

import cv2
import numpy as np

from reflex_bench.data import list_images, sha256_file

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "data" / "REFLEX_SAMPLE_KIT"
VISA = Path(os.environ.get("REFLEX_VISA_PREPARED", str(ROOT / "data" / "visa" / "prepared")))
OUT = ROOT / "reports" / "data_audit.json"


def audit_kit() -> dict:
    manifest = KIT / "manifest.csv"
    rows = list(csv.DictReader(manifest.open(encoding="utf-8-sig", newline="")))
    issues = []
    category_counts: dict[str, dict[str, int]] = {}
    verified = 0
    for row in rows:
        img = KIT / row["path"]
        mask = KIT / row["mask_path"]
        if row.get("is_synthetic", "").lower() != "true":
            issues.append(f"non-synthetic marker: {row.get('case_id')}")
        if not img.is_file() or not mask.is_file():
            issues.append(f"missing asset: {row.get('case_id')}")
            continue
        actual_sha = sha256_file(img)
        if actual_sha != row["sha256"]:
            issues.append(f"image hash mismatch: {row['case_id']}")
        image = cv2.imread(str(img), cv2.IMREAD_COLOR)
        gt = cv2.imread(str(mask), cv2.IMREAD_GRAYSCALE)
        if image is None or gt is None:
            issues.append(f"decode failure: {row['case_id']}")
            continue
        if image.shape[:2] != gt.shape[:2]:
            issues.append(f"image/mask shape mismatch: {row['case_id']}")
        if int(row["label"]) == 0 and np.any(gt):
            issues.append(f"normal mask is nonempty: {row['case_id']}")
        if int(row["label"]) == 1 and not np.any(gt):
            issues.append(f"defect mask is empty: {row['case_id']}")
        cats = category_counts.setdefault(row["category"], {"normal": 0, "defect": 0})
        cats["defect" if int(row["label"]) else "normal"] += 1
        verified += 1
    categories = sorted(category_counts)
    source_archive = Path(os.environ.get("REFLEX_SAMPLE_ARCHIVE", str(ROOT.parent / "reflex-data" / "REFLEX_SAMPLE_IMAGE_KIT.zip")))
    archive_check = {"name": "REFLEX_SAMPLE_IMAGE_KIT.zip", "present_locally": source_archive.is_file(),
                     "sha256": sha256_file(source_archive) if source_archive.is_file() else None,
                     "zip_crc_check": None}
    if source_archive.is_file():
        with zipfile.ZipFile(source_archive) as archive:
            archive_check["zip_crc_check"] = "PASS" if archive.testzip() is None else "FAIL"
    visa = {}
    for category in ("candle", "cashew", "pcb1"):
        root = VISA / category
        if not root.exists():
            visa[category] = {"status": "BLOCKED", "reason": "prepared category is absent"}
            continue
        train = list_images(root / "train" / "good") if (root / "train" / "good").exists() else []
        good = list_images(root / "test" / "good") if (root / "test" / "good").exists() else []
        bad = list_images(root / "test" / "bad") if (root / "test" / "bad").exists() else []
        masks = list((root / "ground_truth" / "bad").glob("*_mask.png")) if (root / "ground_truth" / "bad").exists() else []
        visa[category] = {"status": "AVAILABLE" if train and good and bad and len(masks) == len(bad) else "INCOMPLETE",
                          "train_good": len(train), "test_good": len(good), "test_defect": len(bad), "defect_masks": len(masks),
                          "per_file_hashes": "computed in per_case.csv for used cases", "archive_sha256_verified": False}
    split_csv = ROOT / "data" / "visa" / "1cls.csv"
    return {"synthetic_kit": {"path": "data/REFLEX_SAMPLE_KIT", "source_archive": archive_check,
                              "manifest_sha256": sha256_file(manifest), "rows": len(rows),
                              "verified_rows": verified, "category_counts": category_counts, "issues": issues,
                              "status": "PASS" if not issues and verified == len(rows) else "FAIL"},
            "visa_local_subset": {"root": "external local VisA prepared tree; image data not bundled", "categories": visa,
                                  "official_split_csv": {"path": "data/visa/1cls.csv", "source": "official VisA 1cls.csv copied from local preparation folder",
                                      "present": split_csv.exists(),
                                      "sha256": sha256_file(split_csv) if split_csv.exists() else None},
                                  "full_official_archive_present": False,
                                  "archive_provenance": "per-image provenance; full source archive SHA256 not verified; local prepared subset only"}}


def main() -> None:
    result = audit_kit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["synthetic_kit"]["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
