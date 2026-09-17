"""KEYSTONE CLI. Phase 1 subcommands: fetch, build.

Later phases add: backtest | holdout | project | statcast | diagnostics.
"""
from __future__ import annotations

import argparse
import sys

from keystone import config as C
from keystone.data import build as build_mod
from keystone.data import mlb_api


def _seasons(start: int, end: int) -> list[int]:
    if start > end:
        raise SystemExit(f"--start ({start}) must be <= --end ({end})")
    return list(range(start, end + 1))


def cmd_fetch(args: argparse.Namespace) -> None:
    C.ensure_dirs()
    seasons = _seasons(args.start, args.end)
    print(f"[fetch] seasons {seasons[0]}..{seasons[-1]} (cache: {mlb_api.CACHE})")
    for s in seasons:
        mlb_api.teams(s)
        mlb_api.team_totals(s, "hitting")
        mlb_api.team_totals(s, "pitching")
        traded_h = traded_p = 0
        for group, tag in (("hitting", "H"), ("pitching", "P")):
            df = mlb_api.player_season_stats(s, group)
            for pid in df.loc[df.num_teams > 1, "mlbam_id"].astype(int):
                mlb_api.player_team_splits(int(pid), s, group)
            if tag == "H":
                traded_h = int((df.num_teams > 1).sum())
                h_total = len(df)
            else:
                traded_p = int((df.num_teams > 1).sum())
                p_total = len(df)
        df_h = mlb_api.player_season_stats(s, "hitting")
        df_p = mlb_api.player_season_stats(s, "pitching")
        ids = sorted(set(int(i) for i in list(df_h["mlbam_id"]) + list(df_p["mlbam_id"])))
        mlb_api.people(ids)
        print(f"  {s}: H={h_total} (traded {traded_h}) P={p_total} (traded {traded_p}) bios={len(ids)}")
    print("[fetch] done")


def cmd_build(args: argparse.Namespace) -> None:
    C.ensure_dirs()
    if not C.FG_GUTS_CSV.exists():
        sys.exit(f"[build] missing {C.FG_GUTS_CSV} — see MANUAL.md §4.4")
    seasons = _seasons(args.start, args.end)
    build_mod.build_all(C.PROCESSED, seasons)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="keystone.pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download Stats API responses into data/raw/statsapi/")
    f.add_argument("--start", type=int, default=C.SEASON_START)
    f.add_argument("--end", type=int, default=C.SEASON_END)
    f.set_defaults(func=cmd_fetch)

    b = sub.add_parser("build", help="write processed parquet tables (§4.3)")
    b.add_argument("--start", type=int, default=C.SEASON_START)
    b.add_argument("--end", type=int, default=C.SEASON_END)
    b.set_defaults(func=cmd_build)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
