"""Rolling-origin backtest: Tier 1 (Marcel) vs Tier 2/3 (state-space). MANUAL.md §6.

LEAKAGE IS PREVENTED BY CONSTRUCTION. Every projection for target season T is built from
`train_slice(bundle, T)`, which drops every row with `season >= T` from the player-season,
exposure, league and Guts tables before any model, Marcel run or baseline touches them. The
target season enters this module through exactly two other doors, both scoring inputs rather
than model inputs:

  * `actuals`      — the observed season being scored.
  * `scoring_env`  — the target season's league constants (wOBA weights, kappa, cFIP) plus each
    player's actual PA'/IP. Used identically for every tier, so no tier can gain from them
    (MANUAL §6: "these are environment constants, not player skill").

`tests/test_backtest_leakage.py` asserts that perturbing season-T rows changes no projection.
"""
from __future__ import annotations

import gc
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

from keystone import config as C
from keystone import league as LG
from keystone.components import (PARK_STAGES, HITTER_STAGES, PITCHER_STAGES, derive_hitter,
                                 derive_pitcher, pa_prime, per_pa_from_stage_rates,
                                 simulate_season, stage_counts)
from keystone.data import mlb_api
from keystone.data import statcast as SC
from keystone.models import marcel as MARCEL
from keystone.models import state_space as SS

ROLES = ("H", "P")
ROLE_STAGES = {"H": HITTER_STAGES, "P": PITCHER_STAGES}
STATS = {"H": ["k_pct", "bb_pct", "hr_pct", "babip", "woba"],
         "P": ["k_pct", "bb_pct", "hr_pct", "babip", "fip"]}
KEY_STAT = {"H": "woba", "P": "fip"}
GATE_COV_RANGE = (0.75, 0.85)
GATE_WIN_FRACTION = 0.75                       # >= 3 of 4 dev targets
DIAG_STAT = "_diagnostics"                     # sentinel rows carrying sampler health

SAMPLING = {"dev": dict(draws=500, tune=500, chains=2),
            "quick": dict(draws=150, tune=150, chains=2)}
QUICK = dict(targets=(2024,), roles=("H",), stages=("k", "hr"))


# ---------------------------------------------------------------- data loading

@dataclass
class Bundle:
    """Processed tables held together so that a training slice is one object."""
    ps: dict           # role -> player_season_{role} (modelled population)
    exp: dict          # role -> exposures_{role}
    lg: dict           # role -> league_{role}
    guts: pd.DataFrame
    people: pd.DataFrame


def load_bundle(processed: Path | None = None) -> Bundle:
    d = Path(processed or C.PROCESSED)
    need = ["player_season_H", "player_season_P", "exposures_H", "exposures_P",
            "league_H", "league_P", "guts", "people"]
    missing = [n for n in need if not (d / f"{n}.parquet").exists()]
    if missing:
        raise SystemExit(f"[backtest] missing processed tables {missing} — run `make data` first")

    def rd(n):
        return pd.read_parquet(d / f"{n}.parquet")

    return Bundle(ps={r: rd(f"player_season_{r}") for r in ROLES},
                  exp={r: rd(f"exposures_{r}") for r in ROLES},
                  lg={r: rd(f"league_{r}") for r in ROLES},
                  guts=rd("guts"), people=rd("people"))


def train_slice(b: Bundle, target: int) -> Bundle:
    """THE leakage guard: nothing at or after `target` survives this call."""
    def cut(df):
        return df[df.season < target].reset_index(drop=True)

    return Bundle(ps={r: cut(df) for r, df in b.ps.items()},
                  exp={r: cut(df) for r, df in b.exp.items()},
                  lg={r: cut(df) for r, df in b.lg.items()},
                  guts=cut(b.guts), people=b.people)


def _env_row(df: pd.DataFrame, season: int, cols: list[str]) -> dict:
    """Row for `season`, else the latest earlier season, else the earliest (MANUAL §4.3)."""
    t = df.dropna(subset=cols).drop_duplicates("season").sort_values("season")
    if t.empty:
        raise ValueError(f"no rows carrying {cols}")
    at = t[t.season == season]
    if at.empty:
        earlier = t[t.season < season]
        at = earlier.tail(1) if not earlier.empty else t.head(1)
    return {c: float(at.iloc[0][c]) for c in cols}


def scoring_env(b: Bundle, role: str, target: int) -> dict:
    """Target-season league constants — the same numbers for every tier."""
    env = _env_row(b.guts, target, ["wBB", "wHBP", "w1B", "w2B", "w3B", "wHR"])
    extra = ["sf_rate"] if role == "H" else ["kappa", "c_fip"]
    env.update(_env_row(b.lg[role], target, extra))
    return env


# ---------------------------------------------------------------- one scoring function

def _fip_on_actual_ip(p: dict, env: dict, pa, ip):
    """FIP re-based onto each player's real innings.

    MANUAL §6 requires simulated FIP to use actual IP. Using it for the point projection and for
    the actual as well keeps all three the same function of the rate components, so RMSE compares
    like with like instead of mixing in IP-conversion error.
    """
    r = per_pa_from_stage_rates(p)
    events = 13 * r["hr"] + 3 * (r["bb"] + r["hbp"]) - 2 * r["k"]
    return events * np.asarray(pa, dtype=float) / np.asarray(ip, dtype=float) + env["c_fip"]


def stats_from_stage_probs(p: dict, role: str, env: dict, pa=None, ip=None) -> dict:
    """Conditional stage probabilities -> the stats of MANUAL §6, via the verified derive_*."""
    if role == "H":
        out = derive_hitter(p, env, env["sf_rate"])
    else:
        out = derive_pitcher(p, env["kappa"], env["c_fip"])
        out["fip"] = _fip_on_actual_ip(p, env, pa, ip)
    return {s: out[s] for s in STATS[role]}


def stats_from_counts(counts: dict, role: str, env: dict, ip=None) -> dict:
    """Simulated season counts -> the same stats, through the verified inverse mapping."""
    pa = counts["pa"]
    r = {"k": counts["k"] / pa, "ubb": counts["bb"] / pa, "hbp": counts["hbp"] / pa,
         "hr": counts["hr"] / pa}
    if role == "H":
        r.update({e: counts[e] / pa for e in ("single", "double", "triple")})
    else:
        r["h_bip"] = counts["h_bip"] / pa
    with np.errstate(divide="ignore", invalid="ignore"):
        p = MARCEL.to_stage_probs(r)
        return stats_from_stage_probs(p, role, env, pa=pa, ip=ip)


def actual_stage_probs(ps: pd.DataFrame, role: str, lg: pd.DataFrame, season: int) -> pd.DataFrame:
    """Observed conditional stage probabilities. A stage with zero trials falls back to that
    season's league rate — only reachable for `triple` (a 200-PA season with no 2B and no 3B)."""
    long = stage_counts(ps, role)
    lg_rate = lg[lg.season == season].drop_duplicates("stage").set_index("stage").rate
    wide, idx = {}, None
    for stage in ROLE_STAGES[role]:
        s = long.loc[long.stage == stage].set_index("mlbam_id")
        if idx is None:
            idx = s.index
        s = s.reindex(idx)
        n = s.n.to_numpy(dtype=float)
        wide[stage] = np.where(n > 0, s.y.to_numpy(dtype=float) / np.where(n > 0, n, 1.0),
                               float(lg_rate.get(stage, np.nan)))
    return pd.DataFrame(wide, index=idx)


# ---------------------------------------------------------------- populations

def eval_population(b: Bundle, role: str, target: int) -> np.ndarray:
    """MANUAL §6: PA'/BF' >= 200 in T, plus some history in T-3..T-1."""
    ps = b.ps[role]
    now = ps[ps.season == target]
    qualified = set(now.loc[pa_prime(now, role) >= C.MIN_PA_EVAL, "mlbam_id"])
    hist = ps[ps.season.between(target - 3, target - 1)]
    has_past = set(hist.loc[pa_prime(hist, role) >= 1, "mlbam_id"])
    return np.array(sorted(qualified & has_past), dtype="int64")


# ---------------------------------------------------------------- tier 1 and baselines

def marcel_probs(train: Bundle, role: str, target: int) -> pd.DataFrame:
    ev = MARCEL.events_table(train.ps[role], role)
    ages = mlb_api.season_age(train.people.set_index("mlbam_id").birth_date, target)
    out = MARCEL.marcel(ev, role, target, ages)
    return out.set_index("mlbam_id")[ROLE_STAGES[role]]


def last_season_probs(train: Bundle, role: str, target: int) -> pd.DataFrame:
    """Baseline: last season's observed rates, no regression at all."""
    prev = train.ps[role]
    prev = prev[prev.season == target - 1]
    if prev.empty:
        return pd.DataFrame(columns=ROLE_STAGES[role], dtype=float)
    return actual_stage_probs(prev, role, train.lg[role], target - 1)


def league_probs(train: Bundle, role: str, target: int, ids: np.ndarray) -> pd.DataFrame:
    """Baseline: every player gets the projected league environment."""
    row = {s: 1.0 / (1.0 + math.exp(-LG.projection_logit(train.lg[role], s, target - 1)))
           for s in ROLE_STAGES[role]}
    return pd.DataFrame([row] * len(ids), index=pd.Index(ids, name="mlbam_id"))


# ---------------------------------------------------------------- tier 2 / 3

def _stage_long(train: Bundle, role: str, window: tuple[int, int]) -> pd.DataFrame:
    df = train.ps[role]
    df = df[df.season.between(*window)]
    bad = df.age.isna()
    if bad.any():
        print(f"  [warn] dropped {int(bad.sum())} {role} rows with unknown age (no birth date)")
        df = df[~bad]
    long = stage_counts(df, role)
    long["pa"] = pa_prime(long, role).to_numpy()
    return long


RHAT_WARN = 1.05


def park_exposure_map(exposures: pd.DataFrame | None, window_end: int) -> dict:
    """Expected target-season park exposure = the player's T-1 (window_end) home-venue shares.

    Leakage-safe: season-T teams are not known at projection time in a backtest, so the last
    observed season stands in for them. Players with no T-1 row project park-neutral.
    Returns {mlbam_id: {venue_id: 0.5 * share}} in the form SS.project expects.
    """
    if exposures is None or exposures.empty:
        return {}
    e = exposures[exposures.season == window_end]
    return {int(p): {int(v): 0.5 * float(s) for v, s in zip(g.venue_id, g.share)}
            for p, g in e.groupby("mlbam_id")}


_SCALAR_POP_PARAMS = ("tau", "sigma_pop", "lam", "sigma_age", "park_sd", "sigma_obs")


def _diagnostics(idata) -> dict:
    """Sampler health + posterior mean/sd for the scalar population parameters.

    r_hat/ess need >= 2 chains and are None below that. Missing parameters (e.g. park_sd on a
    non-park stage) come back as None so the sidecar schema stays fixed across stages.
    """
    post = idata.posterior
    out: dict = {}
    for name in _SCALAR_POP_PARAMS:
        if name in post:
            arr = np.asarray(post[name])
            out[f"{name}_mean"] = float(np.mean(arr))
            out[f"{name}_sd"] = float(np.std(arr))
        else:
            out[f"{name}_mean"] = None
            out[f"{name}_sd"] = None

    present = [v for v in _SCALAR_POP_PARAMS if v in post] or \
              [v for v in ("g0",) if v in post]
    max_rhat = None
    if post.sizes.get("chain", 1) > 1 and present:
        r = az.rhat(idata, var_names=present)
        vals = [float(np.nanmax(np.asarray(r[v]))) for v in present
                if np.isfinite(np.asarray(r[v])).any()]
        max_rhat = round(max(vals), 4) if vals else None

    ess_bulk_min = None
    if present:
        try:
            e = az.ess(idata, var_names=present, method="bulk")
            evals = [float(np.nanmin(np.asarray(e[v]))) for v in present
                     if np.isfinite(np.asarray(e[v])).any()]
            ess_bulk_min = float(min(evals)) if evals else None
        except Exception:
            ess_bulk_min = None

    div = int(np.asarray(idata.sample_stats["diverging"]).sum()) \
        if "diverging" in idata.sample_stats else 0
    out.update({"max_rhat": max_rhat, "divergences": div, "ess_bulk_min": ess_bulk_min})
    return out


def _rp_share(ps_p: pd.DataFrame) -> pd.DataFrame:
    """M2a E3: reliever share per pitcher-season = 1 - GS/G (in [0, 1])."""
    g = ps_p.gamesPitched.clip(lower=1)
    return pd.DataFrame({"mlbam_id": ps_p.mlbam_id, "season": ps_p.season,
                         "rp_share": (1.0 - ps_p.gamesStarted / g).clip(0.0, 1.0)})


def fit_stage_draws(train: Bundle, role: str, stage: str, target: int, sampling: dict,
                    indicator: pd.DataFrame | None = None, seed: int = 1,
                    park_aware: bool = True, env_mode: str = "shock",
                    rp_effect: bool = False, innov: str = "normal",
                    obs_noise: bool = True):
    """Fit one stage on the 6-season window ending at target-1.

    Returns (ids, draws, diagnostics) where draws is (n_players, n_draws): the h=1 talent
    probability for the target season. Park stages project into the player's T-1 park
    (park_aware=True, the default): Marcel inherits each player's park implicitly through his
    raw rates, so a park-neutral Tier 2 would be scored against park-inflected actuals with a
    handicap Marcel does not carry. park_aware=False restores the neutral projection.

    Defaults are the M2c locked configuration (obs_noise=True, env_mode="shock"; innov normal,
    no rp_effect). env_mode="mean3", obs_noise=False reproduce the pre-M2 baseline.
    Experiment flags (docs/fable/M2_experiments.md):
      env_mode="recency"  E2: recency+size-weighted league forecast + common env shock in draws
      rp_effect=True      E3: SP/RP covariate on pitcher stages (ignored for role H)
      innov="t4"          E4: Student-t(4) talent innovations
      env_mode="shock"    E6 (M2b): baseline mean3 point forecast + E2's env shock in draws
      obs_noise=True      E5 (M2b): transient season-level logit noise (non-persistent)
    """
    window_end = target - 1
    window = (window_end - C.WINDOW_LEN + 1, window_end)
    long = _stage_long(train, role, window)
    obs = long.loc[long.stage == stage, ["mlbam_id", "season", "age", "pa", "y", "n"]].copy()
    mu = train.lg[role]
    mu = mu.loc[mu.stage == stage].drop_duplicates("season").set_index("season").logit
    obs["mu_league"] = obs.season.map(mu).to_numpy()
    if obs.mu_league.isna().any():
        raise ValueError(f"missing league logit for stage {stage} over {window}")
    if indicator is not None:
        obs = obs.merge(indicator, on=["mlbam_id", "season"], how="left")

    use_role = rp_effect and role == "P"
    role_x = None
    if use_role:
        rp = _rp_share(train.ps["P"])
        obs = obs.merge(rp, on=["mlbam_id", "season"], how="left")
        obs["rp_share"] = obs.rp_share.fillna(rp.rp_share.mean())
        center = float(obs.rp_share.mean())
        obs["x_role"] = obs.rp_share - center
        # projection covariate: last observed rp_share per player, same centring
        last_rp = (rp[rp.season <= window_end].sort_values("season")
                   .groupby("mlbam_id").rp_share.last())
        role_x = {int(p): float(v) - center for p, v in last_rp.items()}

    use_park = stage in PARK_STAGES
    exposures = None
    if use_park:
        e = train.exp[role]
        exposures = e[e.season.between(*window)]

    d = SS.build_stage_data(obs, window_end, exposures)
    model = SS.build_model(d, use_park=use_park, use_indicator=indicator is not None,
                           innov=innov, use_role=use_role, obs_noise=obs_noise)
    idata = SS.fit(model, seed=seed, target_accept=0.95 if indicator is not None else 0.9,
                   **sampling)
    diag = _diagnostics(idata)
    if use_role:
        arr = np.asarray(idata.posterior["delta_role"])
        diag["delta_role_mean"], diag["delta_role_sd"] = float(arr.mean()), float(arr.std())
    if env_mode == "recency":
        mu_proj, mu_sd = LG.projection_logit_recency(train.lg[role], stage, window_end)
    elif env_mode == "shock":
        # E6: keep the baseline 1/1/1 point forecast, add only E2's validated env shock
        mu_proj = LG.projection_logit(train.lg[role], stage, window_end)
        _, mu_sd = LG.projection_logit_recency(train.lg[role], stage, window_end)
    else:
        mu_proj, mu_sd = LG.projection_logit(train.lg[role], stage, window_end), 0.0
    exposure = park_exposure_map(exposures, window_end) if (park_aware and use_park) else None
    players, P = SS.project(idata, d, horizons=1, mu_proj=mu_proj,
                            rng=np.random.default_rng(seed), park_exposure=exposure,
                            mu_sd=mu_sd, role_x=role_x, innov=innov)
    ids, draws = players.mlbam_id.to_numpy(), np.ascontiguousarray(P[:, 0, :])
    del idata, model, d, P
    gc.collect()
    return ids, draws, diag


def tier_draws(train: Bundle, role: str, target: int, stages: list[str], sampling: dict,
               indicators: dict | None = None, seed: int = 1, park_aware: bool = True,
               env_mode: str = "shock", rp_effect: bool = False, innov: str = "normal",
               obs_noise: bool = True):
    """Fit stages one at a time (memory — MANUAL §12) and align them on one player index."""
    raw, diags, ids_common = {}, {}, None
    for stage in stages:
        ids, draws, diag = fit_stage_draws(train, role, stage, target, sampling,
                                           (indicators or {}).get(stage), seed, park_aware,
                                           env_mode=env_mode, rp_effect=rp_effect, innov=innov,
                                           obs_noise=obs_noise)
        raw[stage] = (ids, draws)
        diags[stage] = diag
        ids_common = pd.Index(ids) if ids_common is None else ids_common.intersection(ids)
        rh = diag["max_rhat"]
        flag = "  <-- CHECK" if rh is not None and rh > RHAT_WARN else ""
        print(f"  fit {role}/{stage}: {len(ids)} players, max r_hat {rh}, "
              f"divergences {diag['divergences']}{flag}")
    ids_common = ids_common.to_numpy()
    out = {}
    for stage, (ids, draws) in raw.items():
        pos = pd.Series(np.arange(len(ids)), index=ids)
        out[stage] = draws[pos.loc[ids_common].to_numpy()]
    return ids_common, out, diags


# ---------------------------------------------------------------- metrics

def weighted_metrics(pred, actual, w) -> dict:
    pred, actual, w = (np.asarray(x, dtype=float) for x in (pred, actual, w))
    ok = np.isfinite(pred) & np.isfinite(actual) & np.isfinite(w) & (w > 0)
    if not ok.any():
        return {"n": 0, "rmse": None, "mae": None}
    e = pred[ok] - actual[ok]
    ww = w[ok] / w[ok].sum()
    return {"n": int(ok.sum()),
            "rmse": float(np.sqrt(np.sum(ww * e ** 2))),
            "mae": float(np.sum(ww * np.abs(e)))}


def interval_coverage(P: dict, ids: np.ndarray, actual: pd.DataFrame, role: str, env: dict,
                      pa: pd.Series, ip: pd.Series, seed: int = 7) -> dict:
    """Posterior-predictive coverage at each player's ACTUAL PA'/BF' (MANUAL §6)."""
    rng = np.random.default_rng(seed)
    hits = {s: {50: [], 80: []} for s in STATS[role]}
    for i, pid in enumerate(ids):
        n_pa = int(pa.loc[pid])
        ip_i = float(ip.loc[pid]) if role == "P" else None
        if n_pa <= 0 or (role == "P" and not (ip_i and ip_i > 0)):
            continue
        sim = stats_from_counts(simulate_season({st: P[st][i] for st in P}, n_pa, rng),
                                role, env, ip=ip_i)
        for stat in STATS[role]:
            draws = np.asarray(sim[stat], dtype=float)
            draws = draws[np.isfinite(draws)]
            a = actual.loc[pid, stat]
            if draws.size < 20 or not np.isfinite(a):
                continue
            for lvl, qs in ((50, (25, 75)), (80, (10, 90))):
                lo, hi = np.percentile(draws, qs)
                hits[stat][lvl].append(bool(lo <= a <= hi))
    return {stat: {lvl: (float(np.mean(v)) if v else None) for lvl, v in d.items()}
            for stat, d in hits.items()}


# ---------------------------------------------------------------- sidecars

def _predictions_from_stage_draws(P_keep: dict, role: str, stages: list[str], env: dict,
                                  pa_keep: np.ndarray | None,
                                  ip_keep: np.ndarray | None) -> dict[str, np.ndarray]:
    """(n_players, n_draws) derived-stat draws (or stage-rate draws when partial)."""
    partial = set(stages) != set(ROLE_STAGES[role])
    if partial:
        return {f"stage_{s}": np.asarray(P_keep[s], dtype=float) for s in stages}
    if role == "H":
        out = derive_hitter(P_keep, env, env["sf_rate"])
    else:
        out = derive_pitcher(P_keep, env["kappa"], env["c_fip"])
        r = per_pa_from_stage_rates(P_keep)
        events = 13 * r["hr"] + 3 * (r["bb"] + r["hbp"]) - 2 * r["k"]
        pa_b = np.asarray(pa_keep, dtype=float)[:, None]
        ip_b = np.asarray(ip_keep, dtype=float)[:, None]
        out["fip"] = events * pa_b / ip_b + env["c_fip"]
    return {s: np.asarray(out[s], dtype=float) for s in STATS[role]}


def _sidecar_predictions(target: int, role: str, tier_name: str, stages: list[str],
                         ss_ids: np.ndarray, P: dict, ids: np.ndarray, env: dict,
                         pa: pd.Series, ip: pd.Series) -> list[dict]:
    """Per-player mean/q10/q50/q90 for the tier's stat set. Restricted to the eval intersection
    (players with actuals) so downstream analyses always have something to compare against."""
    pos = pd.Series(np.arange(len(ss_ids)), index=ss_ids)
    keep = np.array([int(i) for i in ids if i in pos.index], dtype="int64")
    if not len(keep):
        return []
    take = pos.loc[keep].to_numpy()
    P_keep = {s: P[s][take] for s in P}
    pa_keep = pa.loc[keep].to_numpy(dtype=float) if role == "P" else None
    ip_keep = ip.loc[keep].to_numpy(dtype=float) if role == "P" else None
    stat_arrays = _predictions_from_stage_draws(P_keep, role, stages, env, pa_keep, ip_keep)
    rows = []
    for stat, arr in stat_arrays.items():
        ok = np.isfinite(arr)
        mean = np.where(ok.any(axis=-1),
                        np.nanmean(np.where(ok, arr, np.nan), axis=-1), np.nan)
        q = np.nanquantile(np.where(ok, arr, np.nan), [0.10, 0.50, 0.90], axis=-1)
        for i, pid in enumerate(keep):
            rows.append({"target": int(target), "role": role, "tier": tier_name,
                         "mlbam_id": int(pid), "stat": stat,
                         "pred_mean": float(mean[i]) if np.isfinite(mean[i]) else None,
                         "q10": float(q[0, i]) if np.isfinite(q[0, i]) else None,
                         "q50": float(q[1, i]) if np.isfinite(q[1, i]) else None,
                         "q90": float(q[2, i]) if np.isfinite(q[2, i]) else None})
    return rows


def _sidecar_posteriors(target: int, role: str, tier_name: str, diags: dict) -> list[dict]:
    rows = []
    for stage, d in diags.items():
        rows.append({"target": int(target), "role": role, "tier": tier_name, "stage": stage,
                     "tau_mean": d.get("tau_mean"), "tau_sd": d.get("tau_sd"),
                     "sigma_pop_mean": d.get("sigma_pop_mean"),
                     "sigma_pop_sd": d.get("sigma_pop_sd"),
                     "lam_mean": d.get("lam_mean"), "lam_sd": d.get("lam_sd"),
                     "sigma_age_mean": d.get("sigma_age_mean"),
                     "sigma_age_sd": d.get("sigma_age_sd"),
                     "park_sd_mean": d.get("park_sd_mean"),
                     "park_sd_sd": d.get("park_sd_sd"),
                     "sigma_obs_mean": d.get("sigma_obs_mean"),
                     "sigma_obs_sd": d.get("sigma_obs_sd"),
                     "ess_bulk_min": d.get("ess_bulk_min"),
                     "max_rhat": d.get("max_rhat"),
                     "divergences": d.get("divergences")})
    return rows


# ---------------------------------------------------------------- one target

def tier3_indicators(role: str, stages: list[str], target: int) -> dict:
    """{stage: DataFrame(mlbam_id, season, ind_y, ind_n)} for the Tier 3 stages in §5.4.

    Stages without a Tier 3 indicator (or with no Savant data on disk) are omitted; the fitter
    then falls back to Tier 2 behaviour for that stage. Anything at or after the target season is
    stripped here so no scoring data can leak into the indicator likelihood.
    """
    out: dict = {}
    for stage in stages:
        ind = SC.load_indicator(role, stage)
        if ind is None or ind.empty:
            continue
        out[stage] = ind[ind.season < target].reset_index(drop=True)
    return out


def run_target(b: Bundle, role: str, target: int, tier: int, stages: list[str],
               sampling: dict, seed: int = 1, park_aware: bool = True,
               env_mode: str = "shock", rp_effect: bool = False,
               innov: str = "normal",
               obs_noise: bool = True) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (score_rows, prediction_rows, posterior_rows). The last two feed the sidecar
    parquets; empty lists when no tier fit ran or the eval population is empty."""
    train = train_slice(b, target)
    env = scoring_env(b, role, target)
    ids = eval_population(b, role, target)
    if len(ids) == 0:
        print(f"  [skip] {role} {target}: empty evaluation population")
        return [], [], []

    obs_t = b.ps[role]
    obs_t = obs_t[(obs_t.season == target) & obs_t.mlbam_id.isin(ids)]
    pa = pd.Series(pa_prime(obs_t, role).to_numpy(dtype=float), index=obs_t.mlbam_id)
    ip = (pd.Series(obs_t.outs.to_numpy(dtype=float) / 3.0, index=obs_t.mlbam_id)
          if role == "P" else pd.Series(dtype=float))
    w = pa.reindex(ids).to_numpy()
    ip_v = ip.reindex(ids).to_numpy() if role == "P" else None

    ap = actual_stage_probs(obs_t, role, b.lg[role], target).reindex(ids)
    actual = pd.DataFrame(stats_from_stage_probs({s: ap[s].to_numpy() for s in ROLE_STAGES[role]},
                                                 role, env, pa=w, ip=ip_v), index=ids)

    rows: list[dict] = []
    mz = marcel_probs(train, role, target)

    def score(tier_name: str, probs: pd.DataFrame, cov: dict | None = None) -> None:
        p = probs.reindex(ids)
        pred = stats_from_stage_probs({s: p[s].to_numpy(dtype=float) for s in ROLE_STAGES[role]},
                                      role, env, pa=w, ip=ip_v)
        for stat in STATS[role]:
            c = (cov or {}).get(stat, {})
            rows.append({"target": target, "role": role, "tier": tier_name, "stat": stat,
                         **weighted_metrics(pred[stat], actual[stat].to_numpy(), w),
                         "cov50": c.get(50), "cov80": c.get(80), "diagnostics": None})

    score("marcel", mz)
    score("last", last_season_probs(train, role, target))
    score("league", league_probs(train, role, target, ids))

    tier_name = f"tier{tier}"
    indicators = tier3_indicators(role, stages, target) if tier == 3 else None
    if tier == 3 and not indicators:
        print(f"  [warn] tier 3 requested for {role} but no Statcast indicator on disk for any of "
              f"{stages} — running Tier 2 fits (labelled tier3)")
    ss_ids, P, diags = tier_draws(train, role, target, stages, sampling,
                                  indicators=indicators, seed=seed, park_aware=park_aware,
                                  env_mode=env_mode, rp_effect=rp_effect, innov=innov,
                                  obs_noise=obs_noise)

    if set(stages) == set(ROLE_STAGES[role]):
        score(tier_name, pd.DataFrame({st: P[st].mean(axis=1) for st in P}, index=ss_ids),
              _coverage_for(P, ss_ids, ids, actual, role, env, pa, ip))
    else:
        print(f"  [partial] {role} {target}: stages {stages} only — reporting stage rates "
              f"instead of derived stats")
        for stage in stages:
            a = ap[stage].to_numpy(dtype=float)
            proj = pd.Series(P[stage].mean(axis=1), index=ss_ids).reindex(ids).to_numpy(dtype=float)
            for tname, pred in ((tier_name, proj), ("marcel", mz[stage].reindex(ids).to_numpy())):
                rows.append({"target": target, "role": role, "tier": tname,
                             "stat": f"stage_{stage}", **weighted_metrics(pred, a, w),
                             "cov50": None, "cov80": None, "diagnostics": None})

    rows.append({"target": target, "role": role, "tier": tier_name, "stat": DIAG_STAT,
                 "n": None, "rmse": None, "mae": None, "cov50": None, "cov80": None,
                 "diagnostics": diags})
    pred_rows = _sidecar_predictions(target, role, tier_name, stages, ss_ids, P, ids, env, pa, ip)
    post_rows = _sidecar_posteriors(target, role, tier_name, diags)
    return rows, pred_rows, post_rows


def _coverage_for(P, ss_ids, ids, actual, role, env, pa, ip) -> dict:
    pos = pd.Series(np.arange(len(ss_ids)), index=ss_ids)
    keep = np.array([i for i in ids if i in pos.index], dtype="int64")
    take = pos.loc[keep].to_numpy()
    return interval_coverage({st: P[st][take] for st in P}, keep, actual, role, env, pa, ip)


# ---------------------------------------------------------------- gates

def compute_gates(rows: list[dict], dev_targets: list[int]) -> tuple[dict, dict]:
    df = pd.DataFrame([r for r in rows if r.get("stat") != DIAG_STAT])
    gates, production = {}, {}
    for role in ROLES:
        gates[role] = {"tier2": None, "tier3": None}
        stat, need = KEY_STAT[role], max(1, round(GATE_WIN_FRACTION * len(dev_targets)))
        for tier, ref in (("tier2", "marcel"), ("tier3", "tier2")):
            if df.empty:
                continue
            sel = df[(df.role == role) & (df.stat == stat) & df.target.isin(dev_targets)]
            a = sel[sel.tier == tier].drop_duplicates("target").set_index("target").rmse
            bl = sel[sel.tier == ref].drop_duplicates("target").set_index("target").rmse
            common = [t for t in dev_targets
                      if t in a.index and t in bl.index and pd.notna(a[t]) and pd.notna(bl[t])]
            if not common:
                continue
            cov = sel[sel.tier == tier].cov80.dropna()
            cov_mean = float(cov.mean()) if len(cov) else None
            ok_cov = cov_mean is not None and GATE_COV_RANGE[0] <= cov_mean <= GATE_COV_RANGE[1]
            wins = sum(1 for t in common if a[t] <= bl[t])
            gates[role][tier] = {"pass": bool(wins >= need and ok_cov), "wins": wins,
                                 "of": len(common), "need": need, "cov80_mean": cov_mean,
                                 "vs": ref, "targets_scored": common}
        t2, t3 = gates[role]["tier2"], gates[role]["tier3"]
        production[role] = ("tier3" if (t3 and t3["pass"]) else
                            "tier2" if (t2 and t2["pass"]) else "marcel")
    return gates, production


# ---------------------------------------------------------------- report / io

def _fmt(v, nd=4):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "     -"
    return f"{v:>6.{nd}f}"


def print_summary(rows: list[dict], gates: dict, production: dict, targets: list[int]) -> None:
    df = pd.DataFrame([r for r in rows if r.get("stat") != DIAG_STAT])
    if df.empty:
        print("[backtest] no scored rows")
        return
    print(f"[backtest] PA-weighted RMSE, averaged over targets {targets}")
    print(f"  {'role':<4} {'stat':<10} {'n':>5} {'marcel':>7} {'tier2':>7} {'tier3':>7} "
          f"{'last':>7} {'league':>7} {'cov50':>6} {'cov80':>6}")
    for role in ROLES:
        sub = df[df.role == role]
        for stat in sorted(sub.stat.unique(), key=lambda s: (s.startswith("stage_"), s)):
            s = sub[sub.stat == stat]
            mean_of = lambda t: (s.loc[s.tier == t, "rmse"].mean() if (s.tier == t).any() else None)
            cov = s[s.tier.isin(("tier2", "tier3"))]
            n = s.n.dropna()
            print(f"  {role:<4} {stat:<10} {int(n.max()) if len(n) else 0:>5} "
                  f"{_fmt(mean_of('marcel'))} {_fmt(mean_of('tier2'))} {_fmt(mean_of('tier3'))} "
                  f"{_fmt(mean_of('last'))} {_fmt(mean_of('league'))} "
                  f"{_fmt(cov.cov50.mean() if len(cov) else None, 2)} "
                  f"{_fmt(cov.cov80.mean() if len(cov) else None, 2)}")
    for role in ROLES:
        bits = [f"{tier}={'PASS' if g['pass'] else 'FAIL'} ({g['wins']}/{g['of']} vs {g['vs']}, "
                f"need {g['need']}, cov80 "
                f"{'n/a' if g['cov80_mean'] is None else round(g['cov80_mean'], 2)})"
                for tier in ("tier2", "tier3") if (g := gates[role].get(tier))]
        print(f"  gates {role} on {KEY_STAT[role]}: " + ("; ".join(bits) or "not evaluated"))
    print("  production_tier: " + "  ".join(f"{r}={production[r]}" for r in ROLES))


def _json_safe(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def write_json(path: Path, rows: list[dict], targets: list[int], gates: dict, production: dict,
               holdout_target: int | None, park_aware: bool = True,
               experiment_flags: dict | None = None) -> dict:
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "targets": sorted(targets), "holdout_target": holdout_target,
               "park_aware_scoring": park_aware,
               "experiment_flags": experiment_flags,
               "rows": rows, "gates": gates, "production_tier": production}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, default=_json_safe))
    print(f"[backtest] wrote {path} ({len(rows)} rows)")
    return payload


def _merge_rows(old: list[dict], new: list[dict]) -> list[dict]:
    """Replace every (target, role, tier) this run recomputed; keep the rest (so a Tier 3 run
    or the holdout run does not discard the dev results already on disk)."""
    touched = {(r["target"], r["role"], r["tier"]) for r in new}
    return [r for r in old
            if (r.get("target"), r.get("role"), r.get("tier")) not in touched] + new


def _write_sidecar(path: Path, new_rows: list[dict], schema_cols: list[str]) -> None:
    """Merge on (target, role, tier) and write the sidecar parquet. Missing schema columns are
    filled with nulls so the frame shape is stable across quick/dev/partial runs."""
    if not new_rows and not path.exists():
        return                                          # nothing to persist
    new_df = pd.DataFrame(new_rows, columns=schema_cols) if new_rows \
        else pd.DataFrame(columns=schema_cols)
    if path.exists():
        old = pd.read_parquet(path)
        for c in schema_cols:
            if c not in old.columns:
                old[c] = None
        if not new_df.empty:
            touched = set((int(t), r, ti)
                          for t, r, ti in zip(new_df.target, new_df.role, new_df.tier))
            mask = np.array([(int(t), r, ti) not in touched
                             for t, r, ti in zip(old.target, old.role, old.tier)])
            old = old.loc[mask]
        combined = pd.concat([old[schema_cols], new_df[schema_cols]], ignore_index=True)
    else:
        combined = new_df[schema_cols]
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(path, index=False)
    print(f"[backtest] wrote {path.name} ({len(combined)} rows)")


PRED_SCHEMA = ["target", "role", "tier", "mlbam_id", "stat",
               "pred_mean", "q10", "q50", "q90"]
POST_SCHEMA = ["target", "role", "tier", "stage",
               "tau_mean", "tau_sd", "sigma_pop_mean", "sigma_pop_sd",
               "lam_mean", "lam_sd", "sigma_age_mean", "sigma_age_sd",
               "park_sd_mean", "park_sd_sd", "sigma_obs_mean", "sigma_obs_sd",
               "ess_bulk_min", "max_rhat", "divergences"]


# ---------------------------------------------------------------- entry point

def run(targets=None, tier: int = 2, quick: bool = False, roles=None, stages=None,
        out: Path | None = None, holdout: bool = False, seed: int = 1,
        park_aware: bool = True, env_mode: str = "shock", rp_effect: bool = False,
        innov: str = "normal", obs_noise: bool = True) -> dict:
    mode = "quick" if quick else "dev"
    sampling = SAMPLING[mode]
    if quick:
        targets = targets or list(QUICK["targets"])
        roles = roles or list(QUICK["roles"])
        stages = stages or list(QUICK["stages"])
    targets = sorted(int(t) for t in (targets or C.DEV_TARGETS))
    roles = list(roles or ROLES)
    if out is None:
        out = C.ARTIFACTS / ("backtest_quick.json" if quick else "backtest.json")
    out = Path(out)

    b = load_bundle()
    flags = dict(env_mode=env_mode, rp_effect=rp_effect, innov=innov, obs_noise=obs_noise)
    print(f"[backtest] mode={mode} tier={tier} targets={targets} roles={roles} "
          f"sampling={sampling} park_aware={park_aware} flags={flags} -> {out.name}")

    new_rows: list[dict] = []
    new_preds: list[dict] = []
    new_posts: list[dict] = []
    for target in targets:
        for role in roles:
            st = list(stages) if stages else list(ROLE_STAGES[role])
            print(f"[backtest] target {target} role {role} stages {st}")
            r, p, po = run_target(b, role, target, tier, st, sampling, seed=seed,
                                  park_aware=park_aware, env_mode=env_mode,
                                  rp_effect=rp_effect, innov=innov, obs_noise=obs_noise)
            new_rows += r
            new_preds += p
            new_posts += po

    old = json.loads(out.read_text()) if out.exists() else {}
    rows = _merge_rows(old.get("rows", []), new_rows)
    all_targets = sorted(set(old.get("targets", [])) | set(targets))
    dev_targets = [t for t in all_targets if t != C.HOLDOUT_TARGET] or targets
    gates, production = compute_gates(rows, dev_targets)
    holdout_target = C.HOLDOUT_TARGET if holdout else old.get("holdout_target")

    print_summary(new_rows, gates, production, targets)
    payload = write_json(out, rows, all_targets, gates, production, holdout_target, park_aware,
                         experiment_flags=flags)

    suffix = "_quick" if quick else ""
    _write_sidecar(out.parent / f"backtest_predictions{suffix}.parquet", new_preds, PRED_SCHEMA)
    _write_sidecar(out.parent / f"backtest_posteriors{suffix}.parquet", new_posts, POST_SCHEMA)
    return payload
