from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("REFLEX_DATA_DIR", ROOT / "data")).resolve()
MODEL_DIR = Path(os.getenv("MODEL_DIR", DATA_DIR / "model")).resolve()
ASSET_DIR = DATA_DIR / "assets"
DB_PATH = DATA_DIR / "inspections.sqlite3"
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
MAX_EDGE = int(os.getenv("MAX_IMAGE_EDGE", "4096"))
MAX_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(20_000_000)))
APP_VERSION = "0.1.0"
