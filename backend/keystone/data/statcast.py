"""Statcast contact-quality indicators (MANUAL.md §4.1 last row, §5.4).

Pulls Baseball Savant's per-player exit-velo/barrels leaderboard via pybaseball, caches each
(role, season) CSV as parquet in `data/raw/statcast/`, and emits the two processed tables

    data/processed/statcast_H.parquet     mlbam_id, season, attempts, barrels, ev95plus
    data/processed/statcast_P.parquet     mlbam_id, season, attempts, barrels, ev95plus

The state-space model reads these through INDICATOR_MAP: for the 3 Tier 3 stages listed in §5.4
we hand the observation frame extra `ind_y`, `ind_n` columns; `state_space.build_model(...,
use_indicator=True)` then fits a joint binomial on the same latent talent theta. Non-Tier-3
stages continue to fit at Tier 2 (`use_indicator=False`, target_accept 0.9).

Fetch is a long job for Daniel (`make statcast`). The agent never calls Savant.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from keystone import config as C

RAW = C.RAW / "statcast"

# (role, stage) -> (numerator column, denominator column) from the Savant leaderboard.
# All 3 use `attempts` = batted-ball events as the denominator, matching the "BBE" language in §4.1.
INDICATOR_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("H", "hr"): ("barrels", "attempts"),
    ("H", "hit_bip"): ("ev95plus", "attempts"),
    ("P", "hr"): ("barrels", "attempts"),
}


def _leaderboard(role: str, season: int) -> pd.DataFrame:
    """Fetch a single (role, season) Savant leaderboard through pybaseball. Not cached here;
    `fetch_seasons` caches the raw parquet so re-runs are free."""
    import pybaseball as pb
    fn = pb.statcast_batter_exitvelo_barrels if role == "H" else pb.statcast_pitcher_exitvelo_barrels
    df = fn(season, minBBE=1)
    keep = ["player_id", "attempts", "barrels", "ev95plus"]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        raise ValueError(f"Savant {role} {season} missing columns {missing}; got {list(df.columns)}")
    out = df[keep].rename(columns={"player_id": "mlbam_id"}).copy()
    out["mlbam_id"] = out["mlbam_id"].astype("int64")
    out["season"] = int(season)
    for c in ("attempts", "barrels", "ev95plus"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype("int64")
    return out[["mlbam_id", "season", "attempts", "barrels", "ev95plus"]]


def fetch_seasons(seasons: list[int]) -> None:
    """Populate `data/raw/statcast/{role}_{year}.parquet`. Skips a season whose file already exists."""
    RAW.mkdir(parents=True, exist_ok=True)
    for role in ("H", "P"):
        for s in seasons:
            path = RAW / f"{role}_{s}.parquet"
            if path.exists():
                continue
            df = _leaderboard(role, s)
            df.to_parquet(path, index=False)
            print(f"  {role} {s}: {len(df)} rows -> {path.name}")


def _load_raw(role: str, seasons: list[int]) -> pd.DataFrame:
    parts = []
    for s in seasons:
        path = RAW / f"{role}_{s}.parquet"
        if path.exists():
            parts.append(pd.read_parquet(path))
    if not parts:
        return pd.DataFrame(columns=["mlbam_id", "season", "attempts", "barrels", "ev95plus"])
    return pd.concat(parts, ignore_index=True)


def build_processed(seasons: list[int], out_dir: Path | None = None) -> None:
    """Concat the raw per-season files and write processed tables. Idempotent."""
    out = out_dir or C.PROCESSED
    out.mkdir(parents=True, exist_ok=True)
    for role in ("H", "P"):
        df = _load_raw(role, seasons)
        df = df.drop_duplicates(["mlbam_id", "season"]).reset_index(drop=True)
        df.to_parquet(out / f"statcast_{role}.parquet", index=False)
        print(f"  processed statcast_{role}: {len(df)} rows, seasons "
              f"{int(df.season.min()) if len(df) else None}..{int(df.season.max()) if len(df) else None}")


def load_indicator(role: str, stage: str, processed: Path | None = None) -> pd.DataFrame | None:
    """Return (mlbam_id, season, ind_y, ind_n) for a Tier 3 stage, or None if the processed
    table is missing / the stage isn't a Tier 3 stage. Rows with ind_n <= 0 are dropped."""
    if (role, stage) not in INDICATOR_MAP:
        return None
    p = Path(processed or C.PROCESSED) / f"statcast_{role}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    y_col, n_col = INDICATOR_MAP[(role, stage)]
    out = df[["mlbam_id", "season"]].copy()
    out["ind_y"] = df[y_col].astype("int64")
    out["ind_n"] = df[n_col].astype("int64")
    return out[out.ind_n > 0].reset_index(drop=True)
