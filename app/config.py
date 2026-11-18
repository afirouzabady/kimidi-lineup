import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Defaults match card_api_test.php so a warm test can run without new secrets.
API_KEY = os.environ.get("CARD_API_KEY", "Vv]QYa4&xo*vUlVbDs")
API_SECRET = os.environ.get("CARD_API_SECRET", "G}TY-C+(o7#r&_fR34")
HOLD_SECONDS = float(os.environ.get("LINEUP_HOLD_SECONDS", "8"))
DEV_SIMULATE = os.environ.get("DEV_SIMULATE", "") == "1"
DATA_DIR = ROOT / "data" / "cards"
STATIC_DIR = ROOT / "static"
