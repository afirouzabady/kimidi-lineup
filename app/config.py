import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Defaults match card_api_test.php so a warm test can run without new secrets.
API_KEY = os.environ.get("CARD_API_KEY", "Vv]QYa4&xo*vUlVbDs")
API_SECRET = os.environ.get("CARD_API_SECRET", "G}TY-C+(o7#r&_fR34")
HOLD_SECONDS = float(os.environ.get("LINEUP_HOLD_SECONDS", "8"))
DEV_SIMULATE = os.environ.get("DEV_SIMULATE", "") == "1"
# One silent stadium clip per lineup. The next 11 players get the next clip.
BACKGROUND_VIDEOS = (
    "https://clickad-rbvla.hs3.ir/kimdi/backgrounds/hill-dickinson.mp4",
    "https://clickad-rbvla.hs3.ir/kimdi/backgrounds/anfield.mp4",
    "https://clickad-rbvla.hs3.ir/kimdi/backgrounds/tottenham.mp4",
    "https://clickad-rbvla.hs3.ir/kimdi/backgrounds/emirates.mp4",
    "https://clickad-rbvla.hs3.ir/kimdi/backgrounds/etihad.mp4",
    "https://clickad-rbvla.hs3.ir/kimdi/backgrounds/aerial.mp4",
)
DATA_DIR = ROOT / "data" / "cards"
STATIC_DIR = ROOT / "static"
