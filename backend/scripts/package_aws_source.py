from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = (
    Path(".dockerignore"),
    Path("docker/backend.Dockerfile"),
    Path("docker/entrypoint.sh"),
    Path("backend/requirements.txt"),
    Path("backend/app"),
    Path("backend/tests"),
    Path("backend/reflex_bench"),
    Path("backend/scripts"),
    Path("frontend"),
    Path("demo"),
    Path("configs"),
)
FORBIDDEN_PARTS = {".git", ".venv", "data", "results", ".aws"}
FORBIDDEN_NAMES = {".env", "inspections.sqlite3"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Package REFLEX source and seeded fixtures for AWS CodeBuild.")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    for relative in INCLUDE:
        path = ROOT / relative
        if not path.exists():
            raise SystemExit(f"Required build input is missing: {relative.as_posix()}")
        if path.is_file():
            files.append(path)
        else:
            files.extend(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"})
    files = sorted(set(files))
    manifest: list[str] = []
    for path in files:
        relative = path.relative_to(ROOT)
        if FORBIDDEN_PARTS.intersection(relative.parts) or path.name in FORBIDDEN_NAMES:
            raise SystemExit(f"Refusing to include local data in AWS source bundle: {relative.as_posix()}")
        manifest.append(relative.as_posix())
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, relative in zip(files, manifest, strict=True):
            archive.write(path, relative)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f"AWS source archive ready: {len(files)} files; sha256={digest}; private local data excluded.")


if __name__ == "__main__":
    main()
