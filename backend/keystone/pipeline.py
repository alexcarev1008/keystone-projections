"""KEYSTONE CLI. Subcommands: fetch, build (P1) · backtest, holdout (P2) · project (P3) · statcast (P6).

Later phases add: diagnostics.
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


def cmd_backtest(args: argparse.Namespace) -> None:
    from keystone.eval import backtest as bt

    C.ensure_dirs()
    bt.run(targets=args.targets, tier=args.tier, quick=args.quick, roles=args.roles,
           stages=args.stages, out=args.out, seed=args.seed)


def cmd_project(args: argparse.Namespace) -> None:
    from keystone import project as proj

    C.ensure_dirs()
    proj.run(window_end=args.window_end, horizons=args.horizons, quick=args.quick,
             out=args.out, seed=args.seed, tier=args.tier)


def cmd_statcast(args: argparse.Namespace) -> None:
    """Populate the raw Savant cache and write processed statcast_{H,P}.parquet (MANUAL §4.1, §5.4)."""
    from keystone.data import statcast as sc

    C.ensure_dirs()
    seasons = _seasons(args.start, args.end)
    print(f"[statcast] seasons {seasons[0]}..{seasons[-1]}  cache: {sc.RAW}")
    sc.fetch_seasons(seasons)
    sc.build_processed(seasons)
    print("[statcast] done")


def cmd_diagnostics(args: argparse.Namespace) -> None:
    """Phase 6.5: write the Fable context pack from what's on disk (no model fits)."""
    from keystone import diagnostics as diag

    C.ensure_dirs()
    diag.run(out=args.out)


def cmd_holdout(args: argparse.Namespace) -> None:
    """The 2025 holdout: allowed exactly once, and only after the gates are on disk."""
    from keystone.eval import backtest as bt

    C.ensure_dirs()
    path = args.out or (C.ARTIFACTS / "backtest.json")
    if not path.exists():
        sys.exit(f"[holdout] {path} not found — run `make backtest` and record the gates first")
    import json

    prev = json.loads(path.read_text())
    if not any(v for role in prev.get("gates", {}).values() for v in role.values()):
        sys.exit("[holdout] no gates recorded yet — MANUAL.md §6 says the holdout runs ONCE, "
                 "after the dev gates are decided")
    if prev.get("holdout_target") is not None and not args.force:
        sys.exit(f"[holdout] already run on {prev['holdout_target']}. The holdout is a one-shot "
                 f"by design; pass --force only if you know why.")
    bt.run(targets=[args.target], tier=args.tier, out=path, holdout=True, seed=args.seed)


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

    k = sub.add_parser("backtest", help="rolling-origin backtest on the dev targets (§6)")
    k.add_argument("--targets", type=int, nargs="+", default=None,
                   help=f"default {list(C.DEV_TARGETS)}")
    k.add_argument("--tier", type=int, default=2, choices=(2, 3))
    k.add_argument("--quick", action="store_true",
                   help="smoke test: 2024, hitters, stages k+hr, 150 draws -> backtest_quick.json")
    k.add_argument("--roles", nargs="+", default=None, choices=("H", "P"))
    k.add_argument("--stages", nargs="+", default=None)
    k.add_argument("--out", type=lambda s: __import__("pathlib").Path(s), default=None)
    k.add_argument("--seed", type=int, default=1)
    k.set_defaults(func=cmd_backtest)

    p = sub.add_parser("project", help="write production artifacts to data/artifacts/ (§7)")
    p.add_argument("--window-end", type=int, default=C.SEASON_END)
    p.add_argument("--horizons", type=int, default=4)
    p.add_argument("--tier", type=int, default=None, choices=(2, 3),
                   help="override the tier fits; default follows backtest.json production_tier")
    p.add_argument("--quick", action="store_true",
                   help="smoke test: hitters, 200 players, 2 stages, 150 draws")
    p.add_argument("--out", type=lambda s: __import__("pathlib").Path(s), default=None)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=cmd_project)

    sc = sub.add_parser("statcast", help="fetch Savant leaderboards and write statcast_{H,P}.parquet")
    sc.add_argument("--start", type=int, default=C.SEASON_START)
    sc.add_argument("--end", type=int, default=C.SEASON_END)
    sc.set_defaults(func=cmd_statcast)

    dg = sub.add_parser("diagnostics", help="write the Fable context pack (Phase 6.5)")
    dg.add_argument("--out", type=lambda s: __import__("pathlib").Path(s),
                    default=C.REPO_ROOT / "docs" / "fable_context")
    dg.set_defaults(func=cmd_diagnostics)

    h = sub.add_parser("holdout", help="score the held-out season once (§6)")
    h.add_argument("--target", type=int, default=C.HOLDOUT_TARGET)
    h.add_argument("--tier", type=int, default=2, choices=(2, 3))
    h.add_argument("--out", type=lambda s: __import__("pathlib").Path(s), default=None)
    h.add_argument("--seed", type=int, default=1)
    h.add_argument("--force", action="store_true")
    h.set_defaults(func=cmd_holdout)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
