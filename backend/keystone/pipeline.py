"""KEYSTONE CLI. Subcommands: fetch, build (P1) · backtest, holdout (P2) · project (P3) · statcast (P6).

Later phases add: diagnostics.
"""
from __future__ import annotations

import argparse
import sys

from keystone import config as C
from keystone.data import build as build_mod
from keystone.data import mlb_api


def _add_model_config_flags(p: argparse.ArgumentParser, env_modes: tuple[str, ...],
                            env_help: str) -> None:
    """M2c locked configuration (docs/fable/M2_experiments.md) as the default, with opt-outs."""
    p.add_argument("--obs-noise", action=argparse.BooleanOptionalAction, default=True,
                   help="M2b E5: transient season-level logit noise (locked default: on; "
                        "--no-obs-noise = pre-M2 model)")
    p.add_argument("--env-mode", default="shock", choices=env_modes, help=env_help)


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
           stages=args.stages, out=args.out, seed=args.seed,
           park_aware=not args.park_neutral, env_mode=args.env_mode,
           rp_effect=args.rp_effect, innov=args.innov, obs_noise=args.obs_noise)


def cmd_project(args: argparse.Namespace) -> None:
    from keystone import project as proj

    C.ensure_dirs()
    proj.run(window_end=args.window_end, horizons=args.horizons, quick=args.quick,
             out=args.out, seed=args.seed, tier=args.tier, obs_noise=args.obs_noise,
             env_mode=args.env_mode)


def cmd_pt_backtest(args: argparse.Namespace) -> None:
    """M3: rolling-origin PT hurdle vs Marcel PT on the dev targets (docs/fable/M3_playing_time.md §3)."""
    import pandas as pd

    from keystone.eval.backtest import load_bundle
    from keystone.models import playing_time as PT

    if any(t >= C.HOLDOUT_TARGET for t in args.targets):
        sys.exit(f"[pt-backtest] refusing targets >= {C.HOLDOUT_TARGET}: the holdout is spent "
                 "(M3 §2 scores dev targets only)")
    b = load_bundle()
    ps = {r: b.ps[r] for r in args.roles}
    res = PT.backtest_pt(ps, tuple(args.targets), seed=args.seed)
    wide = res.pivot_table(index=["role", "target"], columns="model",
                           values=["n", "rmse", "mae", "bias"])
    table = pd.DataFrame({
        "n": wide[("n", "hurdle")].astype(int),
        "marcel_rmse": wide[("rmse", "marcel")], "hurdle_rmse": wide[("rmse", "hurdle")],
        "marcel_mae": wide[("mae", "marcel")], "hurdle_mae": wide[("mae", "hurdle")],
        "marcel_bias": wide[("bias", "marcel")], "hurdle_bias": wide[("bias", "hurdle")],
    })
    brier = res[res.model == "hurdle"].set_index(["role", "target"])[["brier", "brier_base"]]
    table = table.join(brier)
    print(f"[pt-backtest] targets={list(args.targets)} seed={args.seed}")
    with pd.option_context("display.width", 140, "display.float_format", "{:.3f}".format):
        print(table.to_string())
    for role, g in table.groupby(level="role"):
        wins = int((g.hurdle_rmse < g.marcel_rmse).sum())
        print(f"[pt-backtest] {role}: hurdle beats Marcel PT RMSE on {wins}/{len(g)} targets "
              f"(gate: >= 3 of 4)")


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
    # Score the holdout with exactly the model the dev gates were decided on.
    flags = dict(env_mode=args.env_mode, rp_effect=False, innov="normal",
                 obs_noise=args.obs_noise)
    dev_flags = prev.get("experiment_flags") or {}
    if {k: dev_flags.get(k) for k in flags} != flags:
        sys.exit(f"[holdout] model config {flags} does not match the dev backtest in {path.name} "
                 f"(experiment_flags {prev.get('experiment_flags')}). Promote the matching dev run "
                 f"to {path.name} first — the holdout must score the configuration the gates "
                 f"were decided on.")
    bt.run(targets=[args.target], tier=args.tier, out=path, holdout=True, seed=args.seed,
           **flags)


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
    k.add_argument("--park-neutral", action="store_true",
                   help="score Tier 2/3 with park-neutral projections (pre-M1 behaviour)")
    _add_model_config_flags(
        k, ("shock", "mean3", "recency"),
        "league environment forecast (locked default: shock = M2b E6, mean3 point + env shock; "
        "mean3 = pre-M2, no shock; recency = M2a E2, rejected)")
    k.add_argument("--rp-effect", action="store_true",
                   help="M2a E3: SP/RP covariate on pitcher stages (rejected in M2c)")
    k.add_argument("--innov", default="normal", choices=("normal", "t4"),
                   help="M2a E4: talent innovation distribution (t4 rejected in M2c)")
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
    _add_model_config_flags(p, ("shock", "mean3"),
                            "league environment forecast (locked default: shock = mean3 point + "
                            "env shock in the draws; mean3 = pre-M2, no shock)")
    p.set_defaults(func=cmd_project)

    pt = sub.add_parser("pt-backtest", help="M3 playing-time hurdle vs Marcel PT on the dev targets")
    pt.add_argument("--targets", type=int, nargs="+", default=list(C.DEV_TARGETS))
    pt.add_argument("--roles", nargs="+", default=["H", "P"], choices=("H", "P"))
    pt.add_argument("--seed", type=int, default=1)
    pt.set_defaults(func=cmd_pt_backtest)

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
    _add_model_config_flags(h, ("shock", "mean3"),
                            "league environment forecast (locked default: shock); must match "
                            "backtest.json's experiment_flags")
    h.set_defaults(func=cmd_holdout)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
