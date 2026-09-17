"""FastAPI read-only server for KEYSTONE artifacts (MANUAL.md §8).

Loads every parquet + json in `data/artifacts/` into memory at startup. No model code is
imported here. `create_app(artifacts_dir)` is a factory so tests can point at fixture dirs.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from keystone import config as C

KEY_STATS = {"H": ["woba", "k_pct", "bb_pct", "hr_pct", "babip"],
             "P": ["fip", "k_pct", "bb_pct", "hr_pct", "babip"]}
SORT_DEFAULT = {"H": ("woba", "desc", 300.0), "P": ("fip", "asc", 50.0)}
BIO_COLS = ("mlbam_id", "name", "roles", "primary_pos", "bats", "throws",
            "birth_date", "last_team_abbr", "last_season")


def _fold(s: str) -> str:
    """Case- and accent-insensitive fold for substring search."""
    if s is None:
        return ""
    n = unicodedata.normalize("NFKD", str(s))
    return "".join(ch for ch in n if not unicodedata.combining(ch)).lower()


def _clean(v: Any) -> Any:
    """pandas NA / NaN / NaT -> None; numpy scalars -> Python scalars. JSON-safe."""
    if v is None:
        return None
    if isinstance(v, float) and not np.isfinite(v):
        return None
    if isinstance(v, (np.floating,)):
        f = float(v)
        return f if np.isfinite(f) else None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (pd.Timestamp,)):
        return v.date().isoformat()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of JSON-safe dicts (NaN/NaT -> None)."""
    if df is None or df.empty:
        return []
    out: list[dict] = []
    cols = list(df.columns)
    for row in df.itertuples(index=False, name=None):
        out.append({c: _clean(v) for c, v in zip(cols, row)})
    return out


class State:
    def __init__(self, artifacts: Path):
        self.artifacts = Path(artifacts)
        self.players = pd.read_parquet(self.artifacts / "players.parquet")
        self.history = pd.read_parquet(self.artifacts / "history.parquet")
        self.projections = pd.read_parquet(self.artifacts / "projections.parquet")
        self.waterfall = pd.read_parquet(self.artifacts / "waterfall.parquet")
        self.aging = pd.read_parquet(self.artifacts / "aging.parquet")
        self.league = pd.read_parquet(self.artifacts / "league.parquet")
        self.meta = json.loads((self.artifacts / "meta.json").read_text())
        bt = self.artifacts / "backtest.json"
        self.backtest = json.loads(bt.read_text()) if bt.exists() else None

        self.players["_search"] = self.players["name"].map(_fold)
        self.players_by_id = self.players.set_index("mlbam_id", drop=False)
        self.history_ix = self.history.set_index(["mlbam_id", "role"]).sort_index()
        self.proj_ix = self.projections.set_index(["mlbam_id", "role"]).sort_index()
        self.waterfall_ix = self.waterfall.set_index(["mlbam_id", "role"]).sort_index()

        proj_season = int(self.meta.get("projection_season"))
        self.projection_season = proj_season
        self.league_by_role: dict[str, dict[str, float]] = {}
        for role in ("H", "P"):
            sub = self.league[(self.league.role == role) & (self.league.season == proj_season)]
            self.league_by_role[role] = {str(r.stat): _clean(r.value) for r in sub.itertuples()}


def _default_role(state: State, pid: int) -> str:
    row = state.players_by_id.loc[pid] if pid in state.players_by_id.index else None
    if row is None:
        raise HTTPException(status_code=404, detail="player not found")
    roles = str(row["roles"])
    return "H" if "H" in roles else "P"


def create_app(artifacts_dir: Path | None = None) -> FastAPI:
    if artifacts_dir is None:
        artifacts_dir = C.ARTIFACTS
    state = State(artifacts_dir)

    app = FastAPI(title="KEYSTONE", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.keystone = state

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/meta")
    def meta() -> dict:
        return {"meta": state.meta, "backtest": state.backtest}

    @app.get("/api/search")
    def search(q: str = Query(""), limit: int = Query(10, ge=1, le=50)) -> list[dict]:
        needle = _fold(q).strip()
        if not needle:
            return []
        hits = state.players[state.players["_search"].str.contains(needle, na=False)]
        hits = hits.head(limit)
        cols = ["mlbam_id", "name", "roles", "primary_pos", "last_team_abbr"]
        return _records(hits[cols])

    @app.get("/api/leaderboard")
    def leaderboard(
        role: str = Query("H"),
        sort: str | None = Query(None),
        order: str | None = Query(None),
        min_pt: float | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[dict]:
        if role not in ("H", "P"):
            raise HTTPException(status_code=400, detail="role must be H or P")
        default_sort, default_order, default_min_pt = SORT_DEFAULT[role]
        sort = sort or default_sort
        order = (order or default_order).lower()
        min_pt = default_min_pt if min_pt is None else float(min_pt)
        if sort not in KEY_STATS[role]:
            raise HTTPException(status_code=400, detail=f"sort must be one of {KEY_STATS[role]}")

        proj = state.projections
        h1 = proj[(proj.role == role) & (proj.horizon == 1)]
        if h1.empty:
            return []
        stats = KEY_STATS[role]
        wide = h1[h1.stat.isin(stats)].pivot_table(
            index="mlbam_id", columns="stat",
            values=["q10", "q50", "q90"], aggfunc="first")
        pt = h1.drop_duplicates("mlbam_id").set_index("mlbam_id")["pt"]
        age = h1.drop_duplicates("mlbam_id").set_index("mlbam_id")["age"]

        keep = pt[pt >= min_pt].index
        wide = wide.loc[wide.index.intersection(keep)]
        if wide.empty:
            return []

        sort_series = wide[("q50", sort)]
        ascending = order == "asc"
        wide = wide.assign(_sort=sort_series).sort_values("_sort", ascending=ascending)
        wide = wide.head(limit)

        players = state.players_by_id
        rows: list[dict] = []
        for pid in wide.index:
            if pid not in players.index:
                continue
            p = players.loc[pid]
            row: dict[str, Any] = {
                "mlbam_id": int(pid),
                "name": _clean(p["name"]),
                "team": _clean(p["last_team_abbr"]),
                "age": _clean(age.get(pid)),
                "pt": _clean(pt.get(pid)),
            }
            for stat in stats:
                row[stat] = {
                    "q10": _clean(wide.loc[pid, ("q10", stat)]) if ("q10", stat) in wide.columns else None,
                    "q50": _clean(wide.loc[pid, ("q50", stat)]) if ("q50", stat) in wide.columns else None,
                    "q90": _clean(wide.loc[pid, ("q90", stat)]) if ("q90", stat) in wide.columns else None,
                }
            rows.append(row)
        return rows

    @app.get("/api/players/{mlbam_id}")
    def player(mlbam_id: int, role: str | None = Query(None)) -> dict:
        if mlbam_id not in state.players_by_id.index:
            raise HTTPException(status_code=404, detail="player not found")
        bio_row = state.players_by_id.loc[mlbam_id]
        if role is None:
            role = _default_role(state, mlbam_id)
        if role not in ("H", "P"):
            raise HTTPException(status_code=400, detail="role must be H or P")
        if role not in str(bio_row["roles"]):
            raise HTTPException(status_code=404, detail=f"player has no {role} role")

        bio = {c: _clean(bio_row[c]) for c in BIO_COLS if c in bio_row.index}

        key = (mlbam_id, role)
        hist_df = state.history_ix.loc[[key]] if key in state.history_ix.index else state.history.iloc[0:0]
        hist_df = hist_df.reset_index().sort_values("season")
        history = _records(hist_df.drop(columns=["role"], errors="ignore"))

        proj_df = state.proj_ix.loc[[key]] if key in state.proj_ix.index else state.projections.iloc[0:0]
        proj_df = proj_df.reset_index()
        pt_val = None
        if not proj_df.empty:
            pt_h1 = proj_df[proj_df.horizon == 1]["pt"].dropna()
            pt_val = _clean(pt_h1.iloc[0]) if not pt_h1.empty else None
        projections: dict[str, list[dict]] = {}
        for stat, sub in proj_df.groupby("stat"):
            sub = sub.sort_values("horizon")
            projections[str(stat)] = [
                {"season": _clean(r.season), "horizon": _clean(r.horizon), "age": _clean(r.age),
                 "q10": _clean(r.q10), "q25": _clean(r.q25), "q50": _clean(r.q50),
                 "q75": _clean(r.q75), "q90": _clean(r.q90), "mean": _clean(r.mean),
                 "tier": _clean(r.tier)}
                for r in sub.itertuples(index=False)
            ]

        wf_df = state.waterfall_ix.loc[[key]] if key in state.waterfall_ix.index else state.waterfall.iloc[0:0]
        wf_df = wf_df.reset_index().sort_values("step")
        waterfall = _records(wf_df.drop(columns=["role"], errors="ignore"))

        aging_role = state.aging[state.aging.role == role]
        aging_by_stat: dict[str, list[dict]] = {}
        for stat, sub in aging_role.groupby("stat"):
            sub = sub.sort_values("age")
            aging_by_stat[str(stat)] = [{"age": _clean(r.age), "value": _clean(r.value)}
                                        for r in sub.itertuples(index=False)]

        return {
            "bio": bio,
            "role": role,
            "history": history,
            "projections": projections,
            "pt": pt_val,
            "waterfall": waterfall,
            "aging": aging_by_stat,
            "league": state.league_by_role.get(role, {}),
        }

    return app


app = create_app()
