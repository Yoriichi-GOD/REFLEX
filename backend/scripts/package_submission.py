from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = (
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "LICENSE",
    "Makefile",
    "README.md",
    "compose.yaml",
    "backend/app",
    "backend/reflex_bench",
    "backend/requirements.txt",
    "backend/scripts",
    "backend/tests",
    "configs",
    "data/assets_manifest.json",
    "data/visa/1cls.csv",
    "data/REFLEX_SAMPLE_KIT",
    "demo",
    "docker",
    "docs",
    "frontend",
    "infra",
    "results/environment_20261023T193302585414Z.json",
    "results/eval_20261023T193302585414Z.json",
    "results/eval_20261023T193302585414Z.md",
    "results/failures/20261023T193302585414Z/discoloration_00_false_clear_by_agent.png",
    "results/failures/20261023T193302585414Z/discoloration_02_false_clear_by_agent.png",
    "results/failures/20261023T193302585414Z/normal_008_false_defect_by_agent.png",
    "results/latency_20261023T193302585414Z.csv",
    "results/aws-evidence-20261024t034312z.json",
    "results/aws-smoke-20261024t034312z.json",
    "reports/data_audit.json",
    "reports/synthetic_qa/metrics.json",
    "reports/synthetic_qa/per_case.csv",
    "reports/benchmarks/real_visa_summary.json",
    "reports/benchmarks/candle/metrics.json",
    "reports/benchmarks/candle/per_case.csv",
    "reports/benchmarks/cashew/metrics.json",
    "reports/benchmarks/cashew/per_case.csv",
    "reports/benchmarks/galleries/candle",
    "reports/benchmarks/galleries/cashew",
    "reports/robustness/metrics.json",
    "reports/robustness/per_case.csv",
    "reports/benchmarks/aws_synthetic/summary.json",
    "reports/benchmarks/aws_synthetic/samples.csv",
    "reports/benchmarks/aws_synthetic/cloudwatch_summary.json",
    "reports/FINAL_BENCHMARK_REPORT.md",
    "reports/benchmark_environment.json",
    "reports/benchmark_summary.svg",
)
FORBIDDEN_PARTS = {".git", ".aws", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
IMPROVEMENT = "reports/improvement_20261024"
INCLUDE += ("backend/requirements-benchmark.txt",)
INCLUDE += tuple(f"{IMPROVEMENT}/{name}" for name in (
    "REPORT.md", "comparison.json", "freeze.json", "gallery.html", "verification.json", "local_smoke.json",
    "local_app.png", "pretrained_provenance.json", "feature_graph_provenance.json",
))
for improvement_category in ("candle", "cashew"):
    INCLUDE += tuple(f"{IMPROVEMENT}/{improvement_category}/{name}" for name in (
        "metrics.json", "per_case.csv", "membership.json", "development.json", "development.csv", "gallery",
        "robustness_blur_5x5_sigma1_2.csv", "robustness_gaussian_noise_sigma12.csv", "robustness_jpeg_quality35.csv",
        "robustness_brightness_0_78_plus30.csv", "robustness_contrast_1_25.csv", "robustness_rotation_7deg.csv",
        "robustness_resize_0_55_down_up.csv", "robustness_defect_downsize_0_5.csv", "robustness_center_occlusion_20pct.csv",
    ))
    INCLUDE += tuple(f"{IMPROVEMENT}/models/{improvement_category}/{name}" for name in ("metadata.json", "patch_bank.npz"))
FORBIDDEN_NAMES = {".env", "inspections.sqlite3"}
MANIFEST_NAME = "SUBMISSION_MANIFEST.json"


def collect_files() -> list[tuple[Path, str]]:
    files: list[Path] = []
    for relative_text in INCLUDE:
        relative = Path(relative_text)
        path = ROOT / relative
        if not path.exists():
            raise SystemExit(f"Required submission input is missing: {relative.as_posix()}")
        if path.is_file():
            files.append(path)
        else:
            files.extend(
                item
                for item in path.rglob("*")
                if item.is_file()
                and "__pycache__" not in item.parts
                and item.suffix not in {".pyc", ".pyo"}
            )

    archive_files: list[tuple[Path, str]] = []
    for path in sorted(set(files)):
        relative = path.relative_to(ROOT)
        arcname = relative.as_posix()
        if path.is_symlink():
            raise SystemExit(f"Refusing to package a symlink: {arcname}")
        if FORBIDDEN_PARTS.intersection(relative.parts) or path.name in FORBIDDEN_NAMES:
            raise SystemExit(f"Refusing to package private or runtime data: {arcname}")
        if path.suffix.lower() in {".sqlite", ".sqlite3", ".db", ".pem", ".key"}:
            raise SystemExit(f"Refusing to package a database or private key: {arcname}")
        if path.name == MANIFEST_NAME:
            raise SystemExit(f"Reserved generated manifest name already exists: {arcname}")
        archive_files.append((path, arcname))
    return archive_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a submission archive from reviewed source and evidence only.")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "reflex-submission.zip")
    args = parser.parse_args()

    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents and output.name in {"inspections.sqlite3", ".env"}:
        raise SystemExit("Refusing an unsafe output path.")
    output.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files()
    entries = [
        {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
        for path, name in files
    ]
    manifest = {
        "artifact": "REFLEX submission source and evidence",
        "file_count": len(entries),
        "files": entries,
        "exclusions": ["local inspection database and uploads", "AWS credentials", "virtual environments", "unselected historical run outputs"],
    }
    output_manifest = output.with_name("reflex-submission-manifest.json")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, arcname in files:
            archive.write(path, arcname)
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2) + "\n")

    with zipfile.ZipFile(output, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or MANIFEST_NAME not in names:
            raise SystemExit("Submission archive contains duplicate paths or is missing its manifest.")
        for name in names:
            parts = Path(name).parts
            if FORBIDDEN_PARTS.intersection(parts) or Path(name).name in FORBIDDEN_NAMES:
                raise SystemExit(f"Submission archive contains forbidden path: {name}")
            if Path(name).suffix.lower() in {".sqlite", ".sqlite3", ".db", ".pem", ".key"}:
                raise SystemExit(f"Submission archive contains a database or private key: {name}")
        if set(names) != {name for _, name in files} | {MANIFEST_NAME}:
            raise SystemExit("Submission archive contents differ from the reviewed allowlist.")

    archive_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    output_manifest.write_text(
        json.dumps({"archive": output.name, "sha256": archive_sha256, "file_count": len(entries)}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Submission archive: {output}")
    print(f"Files: {len(entries)} source/evidence files plus {MANIFEST_NAME}")
    print(f"SHA-256: {archive_sha256}")
    print("Archive inspection: passed; private databases, credentials, and runtime caches are excluded.")


if __name__ == "__main__":
    main()
