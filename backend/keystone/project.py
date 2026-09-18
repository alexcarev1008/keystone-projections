"""Production artifacts (MANUAL.md §7): writes the parquet + meta.json set the API serves.

At `window_end` (default 2026) fits Tier 2 once per (role, stage) in the M2c locked configuration
(obs-noise + env shock, see `fit_and_project_stage`), projects h = 1..4 seasons, runs Marcel at
target = window_end + 1, and combines them per the gate in `backtest.json`:
  * `tier2`/`tier3` -> use its own draws directly.
  * `marcel`        -> §6 fallback: shift Tier 2 stage draws in logit space so their h=1 median
                       lands on Marcel's h=1 rate. Bands still come from Tier 2's spread; the
                       aging trajectory is Tier 2's. Methodology page must say so plainly.

The API never fits models. Long: 20-40 min on 4 cores. Agent path: `--quick` fits hitters only,
2 stages, 200 players, reduced sampling and writes every artifact file so the schema check passes.
"""
from __future__ import annotations

import gc
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

from keystone import config as C
from keystone import league as LG
from keystone.components import (HITTER_STAGES, PARK_STAGES, PITCHER_STAGES,
                                 derive_hitter, derive_pitcher, pa_prime,
                                 per_pa_from_stage_rates, stage_counts)
from keystone.data import statcast as SC
from keystone.eval.backtest import Bundle, load_bundle, park_exposure_map
from keystone.models import marcel as MARCEL
from keystone.models import playing_time as PT
from keystone.models import state_space as SS

ROLES = ("H", "P")
ROLE_STAGES = {"H": HITTER_STAGES, "P": PITCHER_STAGES}
STATS = {"H": ["k_pct", "bb_pct", "hr_pct", "babip", "avg", "obp", "slg", "iso", "woba"],
         "P": ["k_pct", "bb_pct", "hr_pct", "babip", "k_minus_bb", "fip", "era"]}
KEY_STAT = {"H": "woba", "P": "fip"}
AGING_STATS = {"H": ["k_pct", "bb_pct", "hr_pct", "babip", "woba"],
               "P": ["k_pct", "bb_pct", "hr_pct", "babip", "fip"]}

SAMPLING = {"prod": dict(draws=500, tune=500, chains=4),
            "quick": dict(draws=150, tune=150, chains=2)}
QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]

RHAT_WARN = 1.05

AGE_MIN, AGE_MAX = SS.AGE_MIN, SS.AGE_MAX

# ---------------------------------------------------------------- environment

def latest_env(b: Bundle, role: str, season: int) -> dict:
    """Target-season league constants; falls back to the latest available row if `season` is missing."""
    def row(df, cols):
        t = df.dropna(subset=cols).drop_duplicates("season").sort_values("season")
        at = t[t.season == season]
        if at.empty:
            earlier = t[t.season < season]
            at = earlier.tail(1) if not earlier.empty else t.head(1)
        return {c: float(at.iloc[0][c]) for c in cols}

    env = row(b.guts, ["wBB", "wHBP", "w1B", "w2B", "w3B", "wHR"])
    env.update(row(b.lg[role], ["sf_rate"] if role == "H" else ["kappa", "c_fip"]))
    return env


def derived_stats(stages: dict, role: str, env: dict, pa=None, ip=None) -> dict:
    """Stage probabilities (per-draw arrays) -> the projection stats (§7 columns).

    Same shape in as out; extra scalars go through unchanged. For pitchers, FIP is re-based on
    each player's projected IP (Marcel PT) so the constant works out even when IP is small.
    """
    if role == "H":
        out = derive_hitter(stages, env, env["sf_rate"])
    else:
        out = derive_pitcher(stages, env["kappa"], env["c_fip"])
        out["k_minus_bb"] = out["k_pct"] - out["bb_pct"]
        if pa is not None and ip is not None and np.all(np.asarray(ip) > 0):
            r = per_pa_from_stage_rates(stages)
            fip_events = 13 * r["hr"] + 3 * (r["bb"] + r["hbp"]) - 2 * r["k"]
            out["fip"] = fip_events * np.asarray(pa) / np.asarray(ip) + env["c_fip"]
            out["era"] = out["fip"]        # league FIP == league ERA by construction
        else:
            out["era"] = out["fip"]
    return {s: out[s] for s in STATS[role]}


# ---------------------------------------------------------------- Tier 2 fits at window_end

def _stage_obs(b: Bundle, role: str, stage: str, window: tuple[int, int]) -> pd.DataFrame:
    df = b.ps[role]
    df = df[df.season.between(*window) & df.age.notna()]
    long = stage_counts(df, role)
    long["pa"] = pa_prime(long, role).to_numpy()
    obs = long.loc[long.stage == stage, ["mlbam_id", "season", "age", "pa", "y", "n"]].copy()
    mu = b.lg[role]
    mu = mu.loc[mu.stage == stage].drop_duplicates("season").set_index("season").logit
    obs["mu_league"] = obs.season.map(mu).to_numpy()
    if obs.mu_league.isna().any():
        raise ValueError(f"missing league logit for stage {stage} over {window}")
    return obs


def _diagnostics(idata) -> dict:
    names = [v for v in ("tau", "sigma_pop", "lam", "sigma_age", "g0", "park_sd", "sigma_obs")
             if v in idata.posterior]
    max_rhat = None
    if idata.posterior.sizes.get("chain", 1) > 1:
        r = az.rhat(idata, var_names=names)
        vals = [float(np.nanmax(np.asarray(r[v]))) for v in names if np.isfinite(np.asarray(r[v])).any()]
        max_rhat = round(max(vals), 4) if vals else None
    div = 0
    if "diverging" in idata.sample_stats:
        div = int(np.asarray(idata.sample_stats["diverging"]).sum())
    return {"max_rhat": max_rhat, "divergences": div}


def _cap_players_to_top(obs: pd.DataFrame, exp: pd.DataFrame | None, window_end: int, cap: int):
    """--quick: keep the top-`cap` players by PA' at window_end (falls back to any window season)."""
    key = obs[obs.season == window_end].groupby("mlbam_id").pa.max()
    if len(key) < cap:
        extra = obs.groupby("mlbam_id").pa.max().sort_values(ascending=False)
        keep = list(dict.fromkeys(list(key.sort_values(ascending=False).index) + list(extra.index)))[:cap]
    else:
        keep = key.sort_values(ascending=False).head(cap).index.tolist()
    obs2 = obs[obs.mlbam_id.isin(keep)].reset_index(drop=True)
    exp2 = exp[exp.mlbam_id.isin(keep)].reset_index(drop=True) if exp is not None else None
    return obs2, exp2


@dataclass
class StageFit:
    ids: np.ndarray                    # (n_players,) mlbam_id in projection order
    age_next: np.ndarray               # age at horizon 1
    P_neutral: np.ndarray              # (n_players, horizons, n_draws) — park-neutral talent
    P_park_aware: np.ndarray | None    # (n_players, horizons, n_draws) — park stages only;
                                       # each player projected in his window_end park exposure
                                       # (leakage-safe stand-in for the target season's park)
    venues: list[int]
    g_age: np.ndarray                  # posterior-mean g by age bucket (n_ages,)
    tau_mean: float
    sigma_pop_mean: float
    park_sd_mean: float | None
    sigma_obs_mean: float | None       # None when obs_noise is off
    phi_mean: np.ndarray | None        # (n_venues,)
    mu_proj: float
    mu_sd: float                       # league-environment shock sd (0 under env_mode mean3)
    max_rhat: float | None
    divergences: int


def fit_and_project_stage(b: Bundle, role: str, stage: str, window_end: int, horizons: int,
                           sampling: dict, seed: int, cap: int | None,
                           indicator: pd.DataFrame | None = None, obs_noise: bool = True,
                           env_mode: str = "shock") -> StageFit:
    """Fit one stage at window_end and project h = 1..horizons.

    Defaults are the M2c locked configuration (docs/fable/M2_experiments.md), mirroring
    `eval.backtest.fit_stage_draws` so shipped draws match the validated ones:
      obs_noise=True    E5: transient season-level logit noise; SS.project draws it per horizon
      env_mode="shock"  E6: mean3 point forecast + a common league-environment shock (sigma_env)
    obs_noise=False / env_mode="mean3" restore the pre-M2 model.
    """
    window = (window_end - C.WINDOW_LEN + 1, window_end)
    obs = _stage_obs(b, role, stage, window)
    if indicator is not None:
        ind = indicator[indicator.season.between(*window)]
        obs = obs.merge(ind, on=["mlbam_id", "season"], how="left")
    exp = None
    if stage in PARK_STAGES:
        exp = b.exp[role]
        exp = exp[exp.season.between(*window)]
    if cap is not None:
        obs, exp = _cap_players_to_top(obs, exp, window_end, cap)

    mu_proj = LG.projection_logit(b.lg[role], stage, window_end)
    if env_mode == "shock":
        _, mu_sd = LG.projection_logit_recency(b.lg[role], stage, window_end)
    elif env_mode == "mean3":
        mu_sd = 0.0
    else:
        raise ValueError(f"unknown env_mode {env_mode!r} (production supports shock, mean3)")

    d = SS.build_stage_data(obs, window_end, exp)
    model = SS.build_model(d, use_park=(stage in PARK_STAGES), use_indicator=indicator is not None,
                           obs_noise=obs_noise)
    idata = SS.fit(model, seed=seed, target_accept=0.95 if indicator is not None else 0.9, **sampling)
    diag = _diagnostics(idata)

    # Both projections reseed identically, so park-aware and neutral draws share every env
    # shock / walk step / season-noise draw and differ only by the park term.
    rng = np.random.default_rng(seed)
    players, P_neutral = SS.project(idata, d, horizons=horizons, mu_proj=mu_proj, rng=rng,
                                    mu_sd=mu_sd)

    P_park_aware = None
    if stage in PARK_STAGES:
        park_exp = park_exposure_map(b.exp[role], window_end)
        _, P_park_aware = SS.project(idata, d, horizons=horizons, mu_proj=mu_proj,
                                     rng=np.random.default_rng(seed), park_exposure=park_exp,
                                     mu_sd=mu_sd)

    post = idata.posterior
    stack = lambda v: post[v].stack(s=("chain", "draw")).to_numpy()
    g_age = stack("g_age").mean(axis=-1)
    tau_mean = float(stack("tau").mean())
    sigma_pop_mean = float(stack("sigma_pop").mean())
    park_sd_mean = float(stack("park_sd").mean()) if "park_sd" in post else None
    phi_mean = stack("phi").mean(axis=-1) if "phi" in post else None
    sigma_obs_mean = float(stack("sigma_obs").mean()) if "sigma_obs" in post else None

    rh = diag["max_rhat"]
    flag = "  <-- CHECK" if rh is not None and rh > RHAT_WARN else ""
    obs_txt = f"on (sigma_obs {sigma_obs_mean:.3f})" if sigma_obs_mean is not None else "off"
    print(f"  fit {role}/{stage}: {len(players)} players, max r_hat {rh}, "
          f"divergences {diag['divergences']}{flag}")
    print(f"    config: obs_noise {obs_txt}, env_mode {env_mode} (mu_sd {mu_sd:.4f}), "
          f"tau {tau_mean:.4f}")
    if P_park_aware is not None:
        med_neu = np.median(P_neutral[:, 0, :], axis=-1)
        med_park = np.median(P_park_aware[:, 0, :], axis=-1)
        delta = med_park - med_neu
        print(f"    park-aware h=1 median vs neutral: mean {float(delta.mean()):+.4f}, "
              f"max |delta| {float(np.nanmax(np.abs(delta))):.4f} "
              f"(shipping in tier2/tier3 mode, no-op under marcel-anchor)")

    fit = StageFit(ids=players.mlbam_id.to_numpy(dtype="int64"),
                   age_next=players.age_next.to_numpy(dtype="int64"),
                   P_neutral=np.asarray(P_neutral, dtype=np.float32),
                   P_park_aware=(np.asarray(P_park_aware, dtype=np.float32)
                                 if P_park_aware is not None else None),
                   venues=list(d.venues), g_age=g_age, tau_mean=tau_mean,
                   sigma_pop_mean=sigma_pop_mean, park_sd_mean=park_sd_mean,
                   sigma_obs_mean=sigma_obs_mean, phi_mean=phi_mean, mu_proj=mu_proj,
                   mu_sd=float(mu_sd),
                   max_rhat=rh, divergences=diag["divergences"])
    del idata, model, d, P_neutral, P_park_aware
    gc.collect()
    return fit


# ---------------------------------------------------------------- Marcel h=1

def _marcel_stage_rates(b: Bundle, role: str, target: int) -> pd.DataFrame:
    ev = MARCEL.events_table(b.ps[role], role)
    ages = b.people.set_index("mlbam_id")["birth_date"]
    from keystone.data import mlb_api
    ages = mlb_api.season_age(ages, target)
    out = MARCEL.marcel(ev, role, target, ages).set_index("mlbam_id")[ROLE_STAGES[role]]
    return out


def _marcel_pt(b: Bundle, role: str, target: int) -> pd.Series:
    return MARCEL.marcel_playing_time(b.ps[role], role, target)


# ---------------------------------------------------------------- align + shift

def _align_stage_fits(fits: dict, stages: list[str]) -> np.ndarray:
    """Player ids common to every stage's fit (they usually match; if not, intersect)."""
    common = pd.Index(fits[stages[0]].ids)
    for s in stages[1:]:
        common = common.intersection(pd.Index(fits[s].ids))
    return common.to_numpy(dtype="int64")


def _reindex_fit(fit: StageFit, ids: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    """Slice per-player arrays down to `ids`. Returns (P_neutral, P_park_aware) — the second
    is None on stages the model didn't park-adjust (all pitcher stages, hitter K/BB/HBP)."""
    pos = pd.Series(np.arange(len(fit.ids)), index=fit.ids)
    take = pos.loc[ids].to_numpy()
    park = fit.P_park_aware[take] if fit.P_park_aware is not None else None
    return fit.P_neutral[take], park


def _ship_draws(P_neutral: np.ndarray, P_park_aware: np.ndarray | None,
                stage: str) -> np.ndarray:
    """The draws that ship: park-aware for park stages, neutral otherwise."""
    if stage in PARK_STAGES and P_park_aware is not None:
        return P_park_aware
    return P_neutral


def _anchor_to_marcel(P_neutral: np.ndarray, marcel_rate: np.ndarray) -> np.ndarray:
    """Shift Tier 2 stage draws in logit space so their h=1 median lands on Marcel's rate.

    P_neutral: (n_players, horizons, n_draws). marcel_rate: (n_players,). Returns same shape.
    """
    eps = 1e-9
    x = np.clip(P_neutral.astype(np.float64), eps, 1 - eps)
    logit_x = np.log(x / (1 - x))
    med_h1 = np.median(logit_x[:, 0, :], axis=-1)
    m = np.clip(marcel_rate.astype(np.float64), eps, 1 - eps)
    logit_m = np.log(m / (1 - m))
    delta = (logit_m - med_h1)[:, None, None]
    y = logit_x + delta
    return (1.0 / (1.0 + np.exp(-y))).astype(np.float32)


# ---------------------------------------------------------------- assemble frames

def _quantile_frame(vals: np.ndarray) -> dict:
    """vals: (n_players, n_draws) -> dict of stat quantile arrays keyed q10/q25/q50/q75/q90 + mean."""
    q = np.quantile(vals, QUANTILES, axis=-1)
    return {"mean": vals.mean(axis=-1), "q10": q[0], "q25": q[1], "q50": q[2],
            "q75": q[3], "q90": q[4]}


def projections_frame(fits: dict, marcel: dict, roles: list[str], stage_map: dict,
                       horizons: int, env: dict, prod_tier: dict,
                       projection_season: int, marcel_pt: dict) -> pd.DataFrame:
    """One row per (mlbam_id, role, horizon, stat) with mean/q10..q90/tier/pt."""
    rows = []
    for role in roles:
        stages = stage_map[role]
        role_fits = {s: fits[(role, s)] for s in stages}
        ids = _align_stage_fits(role_fits, stages)
        if len(ids) == 0:
            continue
        m_rates = marcel[role].reindex(ids)
        m_pt = marcel_pt[role].reindex(ids).to_numpy(dtype=float)
        age_next = role_fits[stages[0]].age_next[
            pd.Series(np.arange(len(role_fits[stages[0]].ids)),
                      index=role_fits[stages[0]].ids).loc[ids].to_numpy()
        ]

        # Slice + optionally anchor each stage's per-horizon draws.
        stage_draws = {}
        partial = set(stages) != set(ROLE_STAGES[role])
        for stage in stages:
            P_neutral, P_park = _reindex_fit(role_fits[stage], ids)
            P_ship = _ship_draws(P_neutral, P_park, stage)
            if prod_tier.get(role) == "marcel" and not partial:
                stage_draws[stage] = _anchor_to_marcel(P_ship, m_rates[stage].to_numpy())
            else:
                stage_draws[stage] = P_ship

        for h in range(1, horizons + 1):
            per_stage_h = {s: stage_draws[s][:, h - 1, :] for s in stages}
            if partial:
                # --quick: only some stages fit; report stage-level rates so schema is populated.
                for stage, arr in per_stage_h.items():
                    q = _quantile_frame(arr)
                    for i, pid in enumerate(ids):
                        rows.append({"mlbam_id": int(pid), "role": role,
                                     "season": projection_season + h - 1,
                                     "horizon": h, "age": int(age_next[i] + h - 1),
                                     "stat": f"stage_{stage}",
                                     "mean": float(q["mean"][i]), "q10": float(q["q10"][i]),
                                     "q25": float(q["q25"][i]), "q50": float(q["q50"][i]),
                                     "q75": float(q["q75"][i]), "q90": float(q["q90"][i]),
                                     "tier": prod_tier.get(role, "tier2"),
                                     "pt": float(m_pt[i]) if h == 1 else np.nan})
                continue
            pa = None if role == "H" else m_pt        # PA-like -> BF-like scale for FIP
            ip = None if role == "H" else np.maximum(m_pt, 1.0)
            stats = derived_stats(per_stage_h, role, env, pa=pa, ip=ip)
            for stat_name in STATS[role]:
                q = _quantile_frame(np.asarray(stats[stat_name]))
                for i, pid in enumerate(ids):
                    rows.append({"mlbam_id": int(pid), "role": role,
                                 "season": projection_season + h - 1,
                                 "horizon": h, "age": int(age_next[i] + h - 1),
                                 "stat": stat_name,
                                 "mean": float(q["mean"][i]), "q10": float(q["q10"][i]),
                                 "q25": float(q["q25"][i]), "q50": float(q["q50"][i]),
                                 "q75": float(q["q75"][i]), "q90": float(q["q90"][i]),
                                 "tier": prod_tier.get(role, "tier2"),
                                 "pt": float(m_pt[i]) if h == 1 else np.nan})
    return pd.DataFrame(rows)


def _weighted_hist_rates(b: Bundle, role: str, target: int, ids: np.ndarray) -> pd.DataFrame:
    """§5.5 step 0: 5/4/3 weighted raw rates (Σw·events / Σw·PA'), no regression, no aging."""
    ev = MARCEL.events_table(b.ps[role], role)
    weights = MARCEL.CFG[role]["weights"]
    E = MARCEL.CFG[role]["events"]
    rows = []
    for j, w in enumerate(weights, start=1):
        part = ev[ev.season == target - j].copy()
        part["w"] = w
        rows.append(part)
    if not rows:
        return pd.DataFrame(index=pd.Index(ids, name="mlbam_id"))
    hist = pd.concat(rows, ignore_index=True)
    hist = hist[hist.pa > 0]
    g = hist.assign(wpa=hist.w * hist.pa).groupby("mlbam_id")
    agg = g.apply(lambda d: pd.Series(
        {**{e: (d.w * d[e]).sum() / d.wpa.sum() for e in E}}), include_groups=False)
    out = agg.reindex(ids)
    return out


def waterfall_frame(fits: dict, marcel: dict, roles: list[str], stage_map: dict,
                     env: dict, prod_tier: dict, b: Bundle, window_end: int) -> pd.DataFrame:
    """§5.5: 6 rows per (player, role, key stat). Only the key stat (wOBA / FIP) is emitted."""
    rows = []
    for role in roles:
        stages = stage_map[role]
        if set(stages) != set(ROLE_STAGES[role]):
            continue                                # --quick with partial stages
        role_fits = {s: fits[(role, s)] for s in stages}
        ids = _align_stage_fits(role_fits, stages)
        if len(ids) == 0:
            continue
        pos0 = pd.Series(np.arange(len(role_fits[stages[0]].ids)),
                         index=role_fits[stages[0]].ids).loc[ids].to_numpy()
        age_next = role_fits[stages[0]].age_next[pos0]

        # Step 0: raw 5/4/3 weighted per-PA rates
        raw = _weighted_hist_rates(b, role, window_end + 1, ids)
        raw_stages = {}
        if not raw.dropna(how="all").empty:
            raw_rates = {e: raw[e].fillna(0).to_numpy() for e in raw.columns}
            raw_stages = MARCEL.to_stage_probs(raw_rates)
        else:
            for s in stages:
                raw_stages[s] = np.full(len(ids), np.nan)
        # Derived stat for step 0 (single value per player, not a draw distribution)
        try:
            step0_stats = derived_stats(raw_stages, role, env, pa=None, ip=None)
            step0 = step0_stats[KEY_STAT[role]]
        except Exception:
            step0 = np.full(len(ids), np.nan)

        # Steps 1..5 require per-stage per-player draws. Build them.
        stage_neutral_h1 = {}          # (n_players, n_draws) at h=1 without aging
        stage_aged_h1 = {}             # h=1 with aging (= P_neutral[:, 0, :])
        stage_home_h1 = {}             # h=1 at the player's window_end park exposure
        g_by_stage = {}
        for stage in stages:
            fit = role_fits[stage]
            P_neu, P_park = _reindex_fit(fit, ids)
            stage_aged_h1[stage] = P_neu[:, 0, :]
            stage_home_h1[stage] = P_park[:, 0, :] if P_park is not None else P_neu[:, 0, :]
            g_by_stage[stage] = fit.g_age
            # Undo aging: subtract g[age_next] in logit space to get "no-aging" version.
            eps = 1e-9
            x = np.clip(stage_aged_h1[stage].astype(np.float64), eps, 1 - eps)
            lx = np.log(x / (1 - x))
            g_at_age = fit.g_age[np.clip(age_next - AGE_MIN, 0, AGE_MAX - AGE_MIN)]
            lx_no_age = lx - g_at_age[:, None]
            stage_neutral_h1[stage] = (1.0 / (1.0 + np.exp(-lx_no_age)))

        step1 = derived_stats({s: stage_neutral_h1[s].mean(axis=-1) for s in stages}, role,
                              env, pa=None, ip=None)[KEY_STAT[role]]
        step2 = derived_stats({s: stage_aged_h1[s].mean(axis=-1) for s in stages}, role,
                              env, pa=None, ip=None)[KEY_STAT[role]]
        step3 = np.full(len(ids), np.nan)     # Tier 3 not shipped
        step4 = step2                          # neutral-park projection = step 2 (Tier 2)
        step5 = derived_stats({s: stage_home_h1[s].mean(axis=-1) for s in stages}, role,
                              env, pa=None, ip=None)[KEY_STAT[role]]

        labels_vals = [
            (0, "3-year line (5/4/3 weighted)", step0),
            (1, "Regression to the mean", step1),
            (2, f"Aging (age N)", step2),
            (3, "Statcast contact quality", step3),
            (4, "Neutral-park projection", step4),
            (5, "At home park", step5),
        ]
        for i, pid in enumerate(ids):
            age_i = int(age_next[i])
            for step, label, arr in labels_vals:
                lab = label if step != 2 else f"Aging (age {age_i})"
                v = float(arr[i]) if arr is not None and np.isfinite(arr[i]) else np.nan
                rows.append({"mlbam_id": int(pid), "role": role, "stat": KEY_STAT[role],
                             "step": int(step), "label": lab, "value": v})
    return pd.DataFrame(rows)


def aging_frame(fits: dict, roles: list[str], stage_map: dict, env: dict) -> pd.DataFrame:
    """§5.6: G(age) = cumsum of posterior-mean g; curve rate(age) = invlogit(mu_proj + G(age) - G(27))."""
    rows = []
    ages = np.arange(AGE_MIN, AGE_MAX + 1)
    for role in roles:
        stages = stage_map[role]
        if set(stages) != set(ROLE_STAGES[role]):
            # partial mode: aging still valid per stage; skip derived
            per_stage = {}
            for stage in stages:
                g = fits[(role, stage)].g_age
                mu_proj = fits[(role, stage)].mu_proj
                G = np.cumsum(g)
                G_27 = G[27 - AGE_MIN]
                logit = mu_proj + G - G_27
                per_stage[stage] = 1.0 / (1.0 + np.exp(-logit))
                for age, v in zip(ages, per_stage[stage]):
                    rows.append({"role": role, "stat": stage, "age": int(age), "value": float(v)})
            continue
        per_stage = {}
        for stage in stages:
            g = fits[(role, stage)].g_age
            mu_proj = fits[(role, stage)].mu_proj
            G = np.cumsum(g)
            G_27 = G[27 - AGE_MIN]
            per_stage[stage] = 1.0 / (1.0 + np.exp(-(mu_proj + G - G_27)))
            for age, v in zip(ages, per_stage[stage]):
                rows.append({"role": role, "stat": stage, "age": int(age), "value": float(v)})
        for stat_name in AGING_STATS[role]:
            if stat_name in stages:
                continue      # already emitted as a stage
            per_age = derived_stats({s: per_stage[s] for s in stages}, role, env,
                                    pa=None, ip=None)[stat_name]
            for age, v in zip(ages, per_age):
                rows.append({"role": role, "stat": stat_name, "age": int(age), "value": float(v)})
    return pd.DataFrame(rows)


def history_frame(b: Bundle, ids_by_role: dict) -> pd.DataFrame:
    rows = []
    for role, ids in ids_by_role.items():
        if len(ids) == 0:
            continue
        ps = b.ps[role]
        keep = ps[ps.mlbam_id.isin(ids)].copy()
        if keep.empty:
            continue
        keep["pa_prime"] = pa_prime(keep, role).to_numpy()
        long = stage_counts(keep, role)
        raw = keep[["mlbam_id", "season"]].copy()
        for stage in ROLE_STAGES[role]:
            s = long[long.stage == stage].set_index(["mlbam_id", "season"])
            raw[stage + "_y"] = s["y"].reindex(list(zip(raw.mlbam_id, raw.season))).to_numpy()
            raw[stage + "_n"] = s["n"].reindex(list(zip(raw.mlbam_id, raw.season))).to_numpy()

        raw_pa = keep.set_index(["mlbam_id", "season"])["pa_prime"].reindex(
            list(zip(raw.mlbam_id, raw.season))).to_numpy(dtype=float)
        stages_p = {}
        for stage in ROLE_STAGES[role]:
            y = raw[stage + "_y"].to_numpy(dtype=float)
            n = raw[stage + "_n"].to_numpy(dtype=float)
            stages_p[stage] = np.where(n > 0, y / np.where(n > 0, n, 1), np.nan)

        env_by_season = {int(s): latest_env(b, role, int(s)) for s in raw.season.unique()}

        for i, r in keep.reset_index(drop=True).iterrows():
            s = int(r.season)
            env = env_by_season[s]
            probs = {stage: np.array([stages_p[stage][i]]) for stage in ROLE_STAGES[role]}
            # if a stage rate is NaN (n=0), fall back to the season's league rate
            for stage in ROLE_STAGES[role]:
                if not np.isfinite(probs[stage][0]):
                    lg = b.lg[role]
                    lg_row = lg[(lg.season == s) & (lg.stage == stage)]
                    probs[stage] = np.array([float(lg_row.rate.iloc[0])]) if not lg_row.empty else np.array([np.nan])
            pa_v = float(r.plateAppearances) if role == "H" else float(r.battersFaced)
            ip_v = float(r.outs) / 3.0 if role == "P" else np.nan
            try:
                dv = derived_stats(probs, role, env,
                                    pa=np.array([raw_pa[i]]) if role == "P" else None,
                                    ip=np.array([max(ip_v, 1.0)]) if role == "P" else None)
                dv = {k: float(v[0]) for k, v in dv.items()}
            except Exception:
                dv = {k: np.nan for k in STATS[role]}
            row = {"mlbam_id": int(r.mlbam_id), "role": role, "season": s,
                   "team_abbr": r.team_abbr, "age": int(r.age) if pd.notna(r.age) else None,
                   "pa": pa_v, "ip": ip_v}
            for stage in ROLE_STAGES[role]:
                row[stage + "_y"] = int(raw.iloc[i][stage + "_y"])
                row[stage + "_n"] = int(raw.iloc[i][stage + "_n"])
            row.update(dv)
            rows.append(row)
    return pd.DataFrame(rows)


def players_frame(b: Bundle, ids_by_role: dict) -> pd.DataFrame:
    role_set = {}
    for role, ids in ids_by_role.items():
        for pid in ids:
            role_set.setdefault(int(pid), set()).add(role)
    ppl = b.people.set_index("mlbam_id")
    rows = []
    for pid, roles_here in role_set.items():
        if pid not in ppl.index:
            continue
        p = ppl.loc[pid]
        # last season / team from the H side if present, else P
        last = None
        for role in ("H", "P"):
            if role in roles_here:
                sub = b.ps[role]
                cand = sub[sub.mlbam_id == pid].sort_values("season").tail(1)
                if not cand.empty:
                    last = (int(cand.iloc[0].season), str(cand.iloc[0].team_abbr))
                    break
        rows.append({"mlbam_id": int(pid), "name": p.get("name"),
                     "roles": "HP" if roles_here == {"H", "P"} else next(iter(roles_here)),
                     "primary_pos": p.get("primary_pos"), "bats": p.get("bats"),
                     "throws": p.get("throws"), "birth_date": p.get("birth_date"),
                     "last_team_abbr": last[1] if last else None,
                     "last_season": last[0] if last else None})
    return pd.DataFrame(rows).sort_values("name")


def league_frame(b: Bundle, roles: list[str], window_end: int, horizons: int) -> pd.DataFrame:
    """League averages by (role, season, stat) for reference lines. Includes projection seasons."""
    rows = []
    for role in roles:
        lg = b.lg[role]
        for season in sorted(lg.season.unique().tolist()) + list(range(window_end + 1, window_end + horizons + 1)):
            env = latest_env(b, role, int(season))
            probs = {}
            for stage in ROLE_STAGES[role]:
                r = lg[(lg.season == season) & (lg.stage == stage)]
                if r.empty:
                    r = lg[lg.stage == stage].sort_values("season").tail(1)
                probs[stage] = np.array([float(r.rate.iloc[0])])
            dv = derived_stats(probs, role, env, pa=np.array([600.0]), ip=np.array([120.0]))
            for stat_name, val in dv.items():
                rows.append({"role": role, "season": int(season), "stat": stat_name,
                             "value": float(val[0])})
            for stage in ROLE_STAGES[role]:
                rows.append({"role": role, "season": int(season), "stat": stage,
                             "value": float(probs[stage][0])})
    return pd.DataFrame(rows).drop_duplicates(["role", "season", "stat"])


def meta_dict(fits: dict, roles: list[str], stage_map: dict, window_end: int, horizons: int,
              prod_tier: dict, b: Bundle, model_config: dict | None = None) -> dict:
    stages_summary = {}
    max_rhat = None
    total_divergences = 0
    for role in roles:
        for stage in stage_map[role]:
            f = fits.get((role, stage))
            if f is None:
                continue
            entry = {"tau_mean": f.tau_mean, "sigma_obs_mean": f.sigma_obs_mean,
                     "sigma_env": f.mu_sd, "sigma_pop_mean": f.sigma_pop_mean,
                     "park_sd_mean": f.park_sd_mean, "max_rhat": f.max_rhat,
                     "divergences": f.divergences}
            if stage == "hr" and f.phi_mean is not None and len(f.venues):
                venue_names = _venue_names(b)
                order = np.argsort(f.phi_mean)
                top = [{"venue_id": int(f.venues[i]),
                        "venue_name": venue_names.get(int(f.venues[i])),
                        "phi": float(f.phi_mean[i])} for i in order[-3:][::-1]]
                bot = [{"venue_id": int(f.venues[i]),
                        "venue_name": venue_names.get(int(f.venues[i])),
                        "phi": float(f.phi_mean[i])} for i in order[:3]]
                entry.update({"top_hr_parks": top, "bottom_hr_parks": bot})
            stages_summary[f"{role}/{stage}"] = entry
            if f.max_rhat is not None:
                max_rhat = f.max_rhat if max_rhat is None else max(max_rhat, f.max_rhat)
            total_divergences += int(f.divergences)
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data_through": date.today().isoformat(),
            "window_end": int(window_end),
            "projection_season": int(window_end + 1),
            "horizons": int(horizons),
            "production_tier": prod_tier,
            "model_config": model_config or {"obs_noise": True, "env_mode": "shock"},
            "stages": stages_summary,
            "max_rhat": max_rhat,
            "total_divergences": total_divergences}


def _venue_names(b: Bundle) -> dict:
    """venue_id -> venue_name from the most recent teams() cache (best-effort)."""
    try:
        from keystone.data import mlb_api
        t = mlb_api.teams(int(b.ps["H"].season.max()))
        return {int(v): str(n) for v, n in zip(t.venue_id, t.venue_name)}
    except Exception:
        return {}


# ---------------------------------------------------------------- M3 playing-time outlook

PT_COLS = ["p_play", "pt_expected", "p_regular"]


def pt_outlook_frame(b: Bundle, roles: list[str], projection_season: int, horizons: int,
                     seed: int) -> pd.DataFrame:
    """M3 hurdle (docs/fable/M3_playing_time.md §4): per (mlbam_id, role, horizon) p_play,
    pt_expected (E[PA or IP] incl. the zero branch) and p_regular (P(PT >= 300 PA / 100 IP)).
    Population = any PT in the two seasons before projection_season."""
    parts = []
    for role in roles:
        ps = b.ps[role]
        fit = PT.fit_pt(PT.training_table(ps, role, projection_season), role, seed=seed)
        table = PT.build_pt_table(ps, role, projection_season)
        sim = PT.simulate_horizons(fit, table, horizons=horizons, seed=seed)
        parts.append(sim.assign(role=role))
        h1 = sim[sim.horizon == 1]
        print(f"[project] PT hurdle {role}: {len(table)} players, h1 mean p_play "
              f"{h1.p_play.mean():.3f}, mean pt_expected {h1.pt_expected.mean():.1f}")
    if not parts:
        return pd.DataFrame(columns=["mlbam_id", "role", "horizon"] + PT_COLS)
    out = pd.concat(parts, ignore_index=True)
    out["mlbam_id"] = out.mlbam_id.astype("int64")
    return out[["mlbam_id", "role", "horizon"] + PT_COLS]


def join_pt_outlook(projections: pd.DataFrame, pt: pd.DataFrame) -> pd.DataFrame:
    """Left-join the PT outlook onto projections by (mlbam_id, role, horizon). Players outside
    the PT population get NaN. The Marcel `pt` column (h=1) is left untouched."""
    if projections.empty:
        return projections.assign(**{c: pd.Series(dtype=float) for c in PT_COLS})
    proj = projections.drop(columns=[c for c in PT_COLS if c in projections.columns])
    out = proj.merge(pt, on=["mlbam_id", "role", "horizon"], how="left", validate="many_to_one")
    assert len(out) == len(proj)
    return out


# ---------------------------------------------------------------- schema check + spot checks

SCHEMAS = {
    "players.parquet": {"mlbam_id", "name", "roles", "primary_pos", "bats", "throws",
                        "birth_date", "last_team_abbr", "last_season"},
    "history.parquet": {"mlbam_id", "role", "season", "team_abbr", "age", "pa", "ip"},
    "projections.parquet": {"mlbam_id", "role", "season", "horizon", "age", "stat",
                            "mean", "q10", "q25", "q50", "q75", "q90", "tier", "pt",
                            "p_play", "pt_expected", "p_regular"},
    "waterfall.parquet": {"mlbam_id", "role", "stat", "step", "label", "value"},
    "aging.parquet": {"role", "stat", "age", "value"},
    "league.parquet": {"role", "season", "stat", "value"},
}


def assert_schema(out_dir: Path) -> None:
    for name, must_have in SCHEMAS.items():
        p = out_dir / name
        if not p.exists():
            raise AssertionError(f"missing artifact: {p}")
        cols = set(pd.read_parquet(p).columns)
        missing = must_have - cols
        if missing:
            raise AssertionError(f"{name} missing columns {sorted(missing)}")
    proj = pd.read_parquet(out_dir / "projections.parquet", columns=PT_COLS)
    for c in ("p_play", "p_regular"):
        v = proj[c].dropna()
        if ((v < 0) | (v > 1)).any():
            raise AssertionError(f"projections.parquet {c} outside [0, 1]")
    if (proj.pt_expected.dropna() < 0).any():
        raise AssertionError("projections.parquet pt_expected < 0")
    meta = out_dir / "meta.json"
    if not meta.exists():
        raise AssertionError(f"missing artifact: {meta}")
    for key in ("generated_at", "data_through", "window_end", "projection_season",
                "production_tier", "model_config", "stages", "max_rhat", "total_divergences"):
        if key not in json.loads(meta.read_text()):
            raise AssertionError(f"meta.json missing key {key}")
    print(f"[project] schema check OK: {len(SCHEMAS)} parquet + meta.json")


def _spot_checks(out_dir: Path, b: Bundle) -> None:
    proj = pd.read_parquet(out_dir / "projections.parquet")
    if proj.empty:
        print("[spot] projections.parquet empty — skipping")
        return
    lines = []
    # 3 well-known hitters' h=1 wOBA median + 80% range (Judge 592450, Soto 665742, Alvarez 670541)
    known = {592450: "Aaron Judge", 665742: "Juan Soto", 670541: "Yordan Alvarez"}
    for pid, name in known.items():
        row = proj[(proj.mlbam_id == pid) & (proj.role == "H") & (proj.horizon == 1) & (proj.stat == "woba")]
        if not row.empty:
            r = row.iloc[0]
            lines.append(f"  {name} ({pid}) 2027 wOBA: q50={r.q50:.3f}  q10-q90 [{r.q10:.3f}, {r.q90:.3f}]")
    # Waterfall telescoping (H woba): step 5 - step 0 == sum of consecutive diffs, within .001
    wf = pd.read_parquet(out_dir / "waterfall.parquet")
    wf_H = wf[(wf.role == "H") & (wf.stat == "woba")]
    if not wf_H.empty:
        piv = wf_H.pivot(index="mlbam_id", columns="step", values="value").dropna(how="all")
        if 0 in piv.columns and 5 in piv.columns:
            end = piv[5].to_numpy()
            start = piv[0].to_numpy()
            bar_sum = np.zeros_like(end)
            for a, bcol in zip([0, 1, 2, 4], [1, 2, 4, 5]):
                if a in piv.columns and bcol in piv.columns:
                    bar_sum += (piv[bcol].to_numpy() - piv[a].to_numpy())
            gap = np.nanmax(np.abs((start + bar_sum) - end))
            lines.append(f"  waterfall telescoping max |gap| = {gap:.4f}  (< .001 target)")
    # Bands widen h=1 -> h=4: check q90 - q10 grows for > 95% of players
    key_role_stat = [("H", "woba"), ("P", "fip")]
    for role, stat in key_role_stat:
        sub = proj[(proj.role == role) & (proj.stat == stat)]
        if sub.empty:
            continue
        widths = sub.assign(w=sub.q90 - sub.q10).pivot(index="mlbam_id", columns="horizon", values="w")
        if 1 in widths.columns and 4 in widths.columns:
            grew = ((widths[4] > widths[1]).sum() / len(widths))
            lines.append(f"  {role}/{stat}: bands widen h1->h4 in {grew:.1%} of players")
    # Max r_hat
    meta = json.loads((out_dir / "meta.json").read_text())
    lines.append(f"  max r_hat: {meta.get('max_rhat')} (< 1.05 target); total divergences: "
                 f"{meta.get('total_divergences')}")
    print("[spot]")
    for line in lines[:15]:
        print(line)


# ---------------------------------------------------------------- population

def projection_population(b: Bundle, role: str, window_end: int) -> np.ndarray:
    """§7: every modelled player with PA'/BF' >= 1 in window_end or in either of the two
    seasons before."""
    ps = b.ps[role]
    ps = ps[ps.season.between(window_end - 2, window_end)]
    n = pa_prime(ps, role)
    return np.array(sorted(ps.loc[n >= 1, "mlbam_id"].unique()), dtype="int64")


# ---------------------------------------------------------------- entry

def run(window_end: int = 2026, horizons: int = 4, quick: bool = False,
        out: Path | None = None, seed: int = 1, tier: int | None = None,
        obs_noise: bool = True, env_mode: str = "shock") -> None:
    if out is None:
        # --quick smoke tests write to a sibling dir so they never overwrite production artifacts.
        out = C.ARTIFACTS / "_quick" if quick else C.ARTIFACTS
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    if quick:
        roles = ["H"]
        stage_map = {"H": ["k", "hr"]}
        cap = 200
        sampling = SAMPLING["quick"]
    else:
        roles = ["H", "P"]
        stage_map = {"H": HITTER_STAGES, "P": PITCHER_STAGES}
        cap = None
        sampling = SAMPLING["prod"]

    b = load_bundle()
    bt_path = C.ARTIFACTS / "backtest.json"
    prod_tier = {"H": "tier2", "P": "tier2"}
    if bt_path.exists():
        prod_tier = json.loads(bt_path.read_text()).get("production_tier", prod_tier)
    if tier == 3:
        prod_tier = {r: "tier3" for r in roles}
    fit_tier = tier or (3 if any(v == "tier3" for v in prod_tier.values()) else 2)
    print(f"[project] window_end={window_end} horizons={horizons} quick={quick} "
          f"sampling={sampling} production_tier={prod_tier} fit_tier={fit_tier} "
          f"obs_noise={obs_noise} env_mode={env_mode}")

    fits: dict = {}
    for role in roles:
        for stage in stage_map[role]:
            ind = SC.load_indicator(role, stage) if fit_tier == 3 else None
            if fit_tier == 3 and ind is not None:
                ind = ind[ind.season <= window_end].reset_index(drop=True)
            fits[(role, stage)] = fit_and_project_stage(
                b, role, stage, window_end, horizons, sampling, seed, cap, indicator=ind,
                obs_noise=obs_noise, env_mode=env_mode)

    marcel_rates = {role: _marcel_stage_rates(b, role, window_end + 1) for role in roles}
    marcel_pt = {role: _marcel_pt(b, role, window_end + 1) for role in roles}

    env = {role: latest_env(b, role, window_end + 1) for role in roles}
    # projections_frame handles per-role env internally; pass a single dict-of-dicts by role
    # via a small helper.
    proj_rows = []
    for role in roles:
        pr = projections_frame({(role, s): fits[(role, s)] for s in stage_map[role]},
                               {role: marcel_rates[role]}, [role], {role: stage_map[role]},
                               horizons, env[role], prod_tier,
                               projection_season=window_end + 1,
                               marcel_pt={role: marcel_pt[role]})
        proj_rows.append(pr)
    projections = pd.concat(proj_rows, ignore_index=True) if proj_rows else pd.DataFrame()
    projections = join_pt_outlook(
        projections, pt_outlook_frame(b, roles, window_end + 1, horizons, seed))

    wf_rows = []
    for role in roles:
        wf = waterfall_frame({(role, s): fits[(role, s)] for s in stage_map[role]},
                             {role: marcel_rates[role]}, [role], {role: stage_map[role]},
                             env[role], prod_tier, b, window_end)
        wf_rows.append(wf)
    waterfall = pd.concat(wf_rows, ignore_index=True) if wf_rows else pd.DataFrame()

    aging_rows = []
    for role in roles:
        aging_rows.append(aging_frame(
            {(role, s): fits[(role, s)] for s in stage_map[role]},
            [role], {role: stage_map[role]}, env[role]))
    aging = pd.concat(aging_rows, ignore_index=True) if aging_rows else pd.DataFrame()

    ids_by_role = {role: projection_population(b, role, window_end) for role in roles}
    if quick:
        # Only keep ids that actually appear in a fit (cap applied inside fit_and_project_stage).
        fit_ids = set()
        for role in roles:
            for stage in stage_map[role]:
                fit_ids.update(fits[(role, stage)].ids.tolist())
        ids_by_role = {r: np.array([i for i in ids if int(i) in fit_ids], dtype="int64")
                       for r, ids in ids_by_role.items()}
    history = history_frame(b, ids_by_role)
    players = players_frame(b, ids_by_role)
    league = league_frame(b, roles, window_end, horizons)
    meta = meta_dict(fits, roles, stage_map, window_end, horizons, prod_tier, b,
                     model_config={"obs_noise": bool(obs_noise), "env_mode": env_mode})

    _write_artifacts(out, players, history, projections, waterfall, aging, league, meta)
    assert_schema(out)
    _spot_checks(out, b)


def _ensure_columns(df: pd.DataFrame, cols) -> pd.DataFrame:
    """Guarantee a schema even when the frame is empty (–quick emits empty waterfall/aging)."""
    for c in cols:
        if c not in df.columns:
            df[c] = pd.Series(dtype="object")
    return df[list(cols) + [c for c in df.columns if c not in cols]]


def _write_artifacts(out: Path, players, history, projections, waterfall, aging, league, meta) -> None:
    players = _ensure_columns(players, SCHEMAS["players.parquet"])
    history = _ensure_columns(history, SCHEMAS["history.parquet"])
    projections = _ensure_columns(projections, SCHEMAS["projections.parquet"])
    waterfall = _ensure_columns(waterfall, SCHEMAS["waterfall.parquet"])
    aging = _ensure_columns(aging, SCHEMAS["aging.parquet"])
    league = _ensure_columns(league, SCHEMAS["league.parquet"])
    players.to_parquet(out / "players.parquet", index=False)
    history.to_parquet(out / "history.parquet", index=False)
    projections.to_parquet(out / "projections.parquet", index=False)
    waterfall.to_parquet(out / "waterfall.parquet", index=False)
    aging.to_parquet(out / "aging.parquet", index=False)
    league.to_parquet(out / "league.parquet", index=False)
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"[project] wrote 6 parquet + meta.json to {out}")
