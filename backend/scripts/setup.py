from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from scripts.make_fixtures import build
from app.core.model import fit_normal_bank

build()
data = ROOT / "data" / "synthetic"
fit_normal_bank(sorted((data / "train_normal").glob("*.png")), sorted((data / "calibration_normal").glob("*.png")), ROOT / "data" / "model", source="synthetic")
print("REFLEX synthetic demo profile is ready.")
