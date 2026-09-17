"""Processed tables (MANUAL.md §4.3): parquet outputs under data/processed/.

Season totals come from the bulk /stats endpoint (one row per player, per §4.1). Per-team park exposure
shares come from /people/{id}/stats and are fetched only for the ~100–150 players per season with
numTeams > 1. Everyone else gets a single exposure row at share 1.0.

Every table is keyed by (mlbam_id, role); two-way players (Ohtani) get separate H and P rows.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from keystone import config as C
from keystone.components import stage_counts
from keystone.data import mlb_api
from keystone.league import hitter_constants, pitcher_constants, stage_league_rates


GROUP = {"H": "hitting", "P": "pitching"}
PA_COL = {"H": "plateAppearances", "P": "battersFaced"}


def _pa_prime(df: pd.DataFrame, role: str) -> pd.Series:
    return (df[PA_COL[role]] - df.intentionalWalks - df.sacBunts - df.catchersInterference).clip(lower=0).astype("int64")


def _load_bulk(seasons: list[int], role: str) -> pd.DataFrame:
    frames = [mlb_api.player_season_stats(s, GROUP[role]) for s in seasons]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _load_team_splits(bulk: pd.DataFrame, role: str) -> pd.DataFrame:
    """Per-team PA/BF for players with num_teams > 1. Returns (season, mlbam_id, team_id, pa)."""
    traded = bulk[bulk["num_teams"] > 1][["mlbam_id", "season"]]
    parts = []
    for _, r in traded.iterrows():
        sp = mlb_api.player_team_splits(int(r["mlbam_id"]), int(r["season"]), GROUP[role])
        if not sp.empty:
            parts.append(sp)
    if not parts:
        return pd.DataFrame(columns=["season", "mlbam_id", "team_id", "pa"])
    return pd.concat(parts, ignore_index=True)


def _player_team_frame(bulk: pd.DataFrame, splits: pd.DataFrame, role: str) -> pd.DataFrame:
    """One row per (mlbam_id, season, team_id). For num_teams == 1, team_id = last_team_id and pa = total.
    For num_teams > 1, use the per-team splits. Joins team_abbr and venue_id."""
    single = bulk[bulk["num_teams"] == 1][["season", "mlbam_id", "last_team_id", PA_COL[role]]].copy()
    single = single.rename(columns={"last_team_id": "team_id", PA_COL[role]: "pa"})

    parts = [single]
    if not splits.empty:
        parts.append(splits[["season", "mlbam_id", "team_id", "pa"]])
    pt = pd.concat(parts, ignore_index=True)
    pt = pt[pt["pa"] > 0].reset_index(drop=True)
    pt["team_id"] = pt["team_id"].astype("int64")

    team_frames = []
    for s in pt["season"].unique():
        team_frames.append(mlb_api.teams(int(s))[["season", "team_id", "team_abbr", "venue_id"]])
    tv = pd.concat(team_frames, ignore_index=True)
    return pt.merge(tv, on=["season", "team_id"], how="left")


def _player_season_frame(bulk: pd.DataFrame, pt: pd.DataFrame, people: pd.DataFrame, role: str) -> pd.DataFrame:
    """One row per (mlbam_id, season). team_abbr = '{n}TM' if num_teams > 1 else the single team abbr.
    main_team_id = team with max PA/BF in per-team splits; = last_team_id if single-team."""
    single_abbr = pt.groupby(["mlbam_id", "season"])["team_abbr"].first().rename("single_abbr").reset_index()
    idx = pt.groupby(["mlbam_id", "season"])["pa"].idxmax()
    main = pt.loc[idx, ["mlbam_id", "season", "team_id"]].rename(columns={"team_id": "main_team_id"})

    out = bulk.merge(single_abbr, on=["mlbam_id", "season"], how="left")
    out = out.merge(main, on=["mlbam_id", "season"], how="left")
    out["team_abbr"] = np.where(out["num_teams"] > 1,
                                out["num_teams"].astype(str) + "TM",
                                out["single_abbr"])
    out = out.drop(columns=["single_abbr"])

    p = people[["mlbam_id", "primary_pos", "birth_date", "bats", "throws"]]
    out = out.merge(p, on="mlbam_id", how="left")
    out["age"] = mlb_api.season_age(out["birth_date"], out["season"])
    return out


def _apply_population_filter(ps: pd.DataFrame, role: str) -> pd.DataFrame:
    n = _pa_prime(ps, role)
    if role == "H":
        mask = (n >= C.MIN_PA_MODEL) & (~ps.primary_pos.isin(C.HITTER_POS_EXCLUDE))
    else:
        mask = (n >= C.MIN_BF_MODEL) & (ps.primary_pos.isin(C.PITCHER_POS_INCLUDE))
    return ps.loc[mask].reset_index(drop=True)


def _exposures(pt_mod: pd.DataFrame) -> pd.DataFrame:
    """(mlbam_id, season, venue_id, share) — share of the player's raw PA/BF spent at each venue."""
    d = pt_mod.copy()
    total = d.groupby(["mlbam_id", "season"])["pa"].transform("sum")
    d["share"] = np.where(total > 0, d["pa"] / total.where(total > 0, 1), 0.0)
    exp = d.groupby(["mlbam_id", "season", "venue_id"], as_index=False)["share"].sum()
    return exp


def _filter_pt(pt: pd.DataFrame, ps: pd.DataFrame) -> pd.DataFrame:
    keys = set(zip(ps["mlbam_id"], ps["season"]))
    return pt.loc[[k in keys for k in zip(pt["mlbam_id"], pt["season"])]].reset_index(drop=True)


def _load_guts() -> pd.DataFrame:
    if not C.FG_GUTS_CSV.exists():
        raise FileNotFoundError(
            f"Missing {C.FG_GUTS_CSV}. Save FanGraphs Guts! CSV per MANUAL.md §4.4.")
    df = pd.read_csv(C.FG_GUTS_CSV)
    keep = ["Season", "wOBA", "wOBAScale", "wBB", "wHBP", "w1B", "w2B", "w3B", "wHR", "cFIP"]
    missing = [c for c in keep if c not in df.columns]
    if missing:
        raise ValueError(f"fg_guts.csv missing columns: {missing}")
    return df[keep].rename(columns={"Season": "season"}).sort_values("season").reset_index(drop=True)


def _check_pa_totals(bulk_H: pd.DataFrame, seasons: list[int]) -> None:
    for s in seasons:
        tt = mlb_api.team_totals(s, "hitting")
        team_pa = int(tt["plateAppearances"].sum())
        player_pa = int(bulk_H.loc[bulk_H.season == s, "plateAppearances"].sum())
        diff = abs(team_pa - player_pa) / max(team_pa, 1)
        print(f"  {s} PA sanity: player={player_pa} team={team_pa} diff={diff:.4%}")
        if diff > 0.01:
            raise AssertionError(f"season {s} PA mismatch: player={player_pa} team={team_pa}")


def _check_modelled_counts(ps: pd.DataFrame, role: str, seasons: list[int]) -> None:
    current_year = pd.Timestamp.today().year
    for s in seasons:
        n = int((ps.season == s).sum())
        if s == 2020:
            need = 400
        elif s >= current_year:
            need = 0            # season in progress
        else:
            need = 600
        marker = "OK" if n >= need else "LOW"
        print(f"  {role} modelled {s}: {n} ({marker}; need >= {need})")
        if n < need:
            raise AssertionError(f"season {s} {role} modelled count {n} < {need}")


def build_all(out_dir: Path, seasons: list[int]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[build] seasons {seasons[0]}..{seasons[-1]} -> {out_dir}")

    bulk_H = _load_bulk(seasons, "H")
    bulk_P = _load_bulk(seasons, "P")
    if bulk_H.empty or bulk_P.empty:
        raise RuntimeError("no cached player_season_stats — run pipeline.py fetch first")

    print("[build] sanity: player PA (bulk) vs team totals PA")
    _check_pa_totals(bulk_H, seasons)

    all_ids = sorted(set(int(i) for i in pd.concat([bulk_H["mlbam_id"], bulk_P["mlbam_id"]]).dropna().unique()))
    print(f"[build] fetching bios for {len(all_ids)} players")
    people = mlb_api.people(all_ids)

    print("[build] fetching per-team splits for traded players")
    splits_H = _load_team_splits(bulk_H, "H")
    splits_P = _load_team_splits(bulk_P, "P")
    print(f"  H splits rows={len(splits_H)}  P splits rows={len(splits_P)}")

    pt_H = _player_team_frame(bulk_H, splits_H, "H")
    pt_P = _player_team_frame(bulk_P, splits_P, "P")
    pt_H.to_parquet(out_dir / "player_team_season_H.parquet", index=False)
    pt_P.to_parquet(out_dir / "player_team_season_P.parquet", index=False)

    ps_H_all = _player_season_frame(bulk_H, pt_H, people, "H")
    ps_P_all = _player_season_frame(bulk_P, pt_P, people, "P")

    print("[build] sanity: no negative stage counts")
    stage_counts(ps_H_all, "H")
    stage_counts(ps_P_all, "P")

    ps_H = _apply_population_filter(ps_H_all, "H")
    ps_P = _apply_population_filter(ps_P_all, "P")
    ps_H.to_parquet(out_dir / "player_season_H.parquet", index=False)
    ps_P.to_parquet(out_dir / "player_season_P.parquet", index=False)

    print("[build] sanity: modelled population size")
    _check_modelled_counts(ps_H, "H", seasons)
    _check_modelled_counts(ps_P, "P", seasons)

    pt_H_mod = _filter_pt(pt_H, ps_H)
    pt_P_mod = _filter_pt(pt_P, ps_P)
    _exposures(pt_H_mod).to_parquet(out_dir / "exposures_H.parquet", index=False)
    _exposures(pt_P_mod).to_parquet(out_dir / "exposures_P.parquet", index=False)

    people.to_parquet(out_dir / "people.parquet", index=False)

    lg_H = stage_league_rates(ps_H, "H").merge(hitter_constants(ps_H), on="season", how="left")
    lg_P = stage_league_rates(ps_P, "P").merge(pitcher_constants(ps_P_all), on="season", how="left")
    lg_H.to_parquet(out_dir / "league_H.parquet", index=False)
    lg_P.to_parquet(out_dir / "league_P.parquet", index=False)

    _load_guts().to_parquet(out_dir / "guts.parquet", index=False)

    files = sorted(p.name for p in out_dir.glob("*.parquet"))
    print(f"[build] wrote {len(files)} parquet files: {', '.join(files)}")
