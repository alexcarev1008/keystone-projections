"""Seasons, paths, and constants that everything else imports (MANUAL.md §4, §5)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
ARTIFACTS = DATA / "artifacts"
EXTERNAL = DATA / "external"
FG_GUTS_CSV = EXTERNAL / "fg_guts.csv"

SEASON_START = 2015
SEASON_END = 2026
WINDOW_LEN = 6                       # a model window is window_end-5 .. window_end
DEV_TARGETS = (2021, 2022, 2023, 2024)
HOLDOUT_TARGET = 2025

MIN_PA_MODEL = 1                     # modelled population lower bound (§4.3)
MIN_BF_MODEL = 1
MIN_PA_EVAL = 200                    # evaluation population (§6)

HITTER_POS_EXCLUDE = {"P"}           # pitchers who bat aren't hitters; TWP is kept
PITCHER_POS_INCLUDE = {"P", "TWP"}


def ensure_dirs() -> None:
    for d in (RAW, PROCESSED, ARTIFACTS, EXTERNAL):
        d.mkdir(parents=True, exist_ok=True)
