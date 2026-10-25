from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

VISA_CLASSES = {
    "candle", "capsules", "cashew", "chewinggum", "fryum",
    "macaroni1", "macaroni2", "pcb1", "pcb2", "pcb3", "pcb4", "pipe_fryum",
}
SPLIT_SOURCE = "https://github.com/amazon-science/spot-diff/blob/main/split_csv/1cls.csv"
DATASET_SOURCE = "https://registry.opendata.aws/visa/"
ARCHIVE_SOURCE = "https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar"
LICENSE = "CC BY 4.0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_dataset_file(dataset_dir: Path, relative_posix_path: str) -> Path:
    relative = PurePosixPath(relative_posix_path.replace("\\", "/"))
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe path in official split file: {relative_posix_path!r}")
    root = dataset_dir.resolve()
    candidate = root.joinpath(*relative.parts).resolve()
    if root not in candidate.parents or not candidate.is_file():
        raise FileNotFoundError(f"Dataset image referenced by split file is missing or outside dataset root: {relative_posix_path}")
    return candidate


def materialize(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if os.path.samefile(source, destination):
            return
        if sha256_file(source) == sha256_file(destination):
            return
        raise FileExistsError(f"Refusing to replace different prepared data: {destination}")
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def binary_mask(source: Path, destination: Path) -> None:
    mask = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    if mask is None:
        raise ValueError(f"Could not decode VisA mask: {source}")
    foreground = np.any(mask != 0, axis=2) if mask.ndim == 3 else mask != 0
    binary = np.where(foreground, 255, 0).astype(np.uint8)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing = cv2.imread(str(destination), cv2.IMREAD_GRAYSCALE)
        if existing is not None and np.array_equal(existing, binary):
            return
        raise FileExistsError(f"Refusing to replace different prepared mask: {destination}")
    if not cv2.imwrite(str(destination), binary):
        raise OSError(f"Could not write prepared mask: {destination}")


def prepare(dataset_dir: Path, split_file: Path, output_dir: Path, class_name: str, archive: Path | None) -> dict:
    if class_name not in VISA_CLASSES:
        raise ValueError(f"Unknown VisA category {class_name!r}. Expected one of: {', '.join(sorted(VISA_CLASSES))}")
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Extracted VisA dataset root not found: {dataset_dir}")
    if not split_file.is_file():
        raise FileNotFoundError(f"Official one-class split CSV not found: {split_file}")
    if archive is not None and not archive.is_file():
        raise FileNotFoundError(f"Archive not found: {archive}")

    output_category = output_dir / class_name
    file_records: list[dict] = []
    counts: dict[str, int] = {"train_normal": 0, "test_normal": 0, "test_anomaly": 0}
    with split_file.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"object", "split", "label", "image", "mask"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Split CSV must contain columns {sorted(required)}")
        for row in reader:
            if row["object"].strip() != class_name:
                continue
            split = row["split"].strip().lower()
            label = row["label"].strip().lower()
            image_rel = row["image"].strip()
            image_src = resolve_dataset_file(dataset_dir, image_rel)
            if split == "train" and label == "normal":
                image_dst = output_category / "train" / "good" / image_src.name
                counts["train_normal"] += 1
            elif split == "test" and label == "normal":
                image_dst = output_category / "test" / "good" / image_src.name
                counts["test_normal"] += 1
            elif split == "test" and label == "anomaly":
                image_dst = output_category / "test" / "bad" / image_src.name
                counts["test_anomaly"] += 1
            else:
                raise ValueError(f"Unsupported official VisA split row: split={split!r}, label={label!r}")
            materialize(image_src, image_dst)
            record = {
                "split": split,
                "label": label,
                "image": image_rel,
                "prepared_image": image_dst.relative_to(output_dir).as_posix(),
                "image_sha256": sha256_file(image_src),
            }
            if label == "anomaly":
                mask_rel = row["mask"].strip()
                if not mask_rel:
                    raise ValueError(f"Official anomaly row has no mask: {image_rel}")
                mask_src = resolve_dataset_file(dataset_dir, mask_rel)
                mask_dst = output_category / "ground_truth" / "bad" / f"{image_src.stem}_mask.png"
                binary_mask(mask_src, mask_dst)
                record["mask"] = mask_rel
                record["prepared_mask"] = mask_dst.relative_to(output_dir).as_posix()
                record["mask_sha256"] = sha256_file(mask_src)
                record["prepared_mask_sha256"] = sha256_file(mask_dst)
            file_records.append(record)

    if not counts["train_normal"] or not counts["test_normal"] or not counts["test_anomaly"]:
        raise ValueError(f"No complete official split found for {class_name}: {counts}")

    manifest = {
        "schema_version": 1,
        "dataset": "Visual Anomaly (VisA), 2022-09-22 release",
        "dataset_source": DATASET_SOURCE,
        "archive_source": ARCHIVE_SOURCE,
        "archive_sha256": sha256_file(archive) if archive else None,
        "license": LICENSE,
        "attribution": "Yang Zou, Jongheon Jeong, Latha Pemula, Dongqing Zhang, and Onkar Dabeer, SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection and Segmentation, ECCV 2022.",
        "split": "Official Amazon Science one-class split",
        "split_source": SPLIT_SOURCE,
        "split_file_sha256": sha256_file(split_file),
        "class_name": class_name,
        "counts": counts,
        "prepared_layout": "MVTec-compatible train/good, test/good, test/bad, ground_truth/bad; anomaly masks binarized to 0/255.",
        "images": file_records,
    }
    manifest_path = output_category / "dataset_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one VisA class using Amazon Science's official one-class split.")
    parser.add_argument("--dataset-dir", required=True, type=Path, help="Root of the extracted VisA archive")
    parser.add_argument("--split-file", required=True, type=Path, help="Official spot-diff split_csv/1cls.csv")
    parser.add_argument("--output-dir", required=True, type=Path, help="Prepared benchmark root; keep outside the repository")
    parser.add_argument("--class-name", required=True, choices=sorted(VISA_CLASSES))
    parser.add_argument("--archive", type=Path, default=None, help="Optional original VisA_20220922.tar for SHA256 provenance")
    args = parser.parse_args()
    manifest = prepare(args.dataset_dir, args.split_file, args.output_dir, args.class_name, args.archive)
    print(json.dumps({"class_name": args.class_name, "counts": manifest["counts"], "split_file_sha256": manifest["split_file_sha256"], "archive_sha256": manifest["archive_sha256"], "output": str(args.output_dir / args.class_name)}, indent=2))


if __name__ == "__main__":
    main()
