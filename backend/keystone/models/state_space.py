"""Tier 2/3 model: Bayesian state-space ("random-walk talent") model for ONE binomial stage.

VERIFIED REFERENCE (simulated MLB-scale test: ~6.4k latent states, 0 divergences on 2 cores,
calibrated, beats a regressed-average baseline). Extend, don't rewrite.

For player i and season t (every season from his first observed season in the window to window_end):

    theta[i, first] = lam * z(log PA' in first observed season) + sigma_pop * e      (talent prior; PA carries info)
    theta[i, t]     = theta[i, t-1] + g[age(i, t)] + tau * e                         (talent drifts + ages)
    y[i, t] ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t] + X_park[i, t] . phi))

  * mu_league[t] is FIXED at the league logit rate for that stage/season (handles run environment).
  * g is the expected year-over-year logit change at each age (a smooth random walk over ages 20-40);
    its cumulative sum is the aging curve. Learned jointly from every season (no paired-season data loss like
    the delta method); the log-PA talent prior absorbs part of the selection effect. Remaining survivor bias
    (players who vanish after bad years) is a documented limitation.
  * tau is the year-to-year talent volatility -> learned recency weighting (large tau = recent seasons matter more).
  * phi are venue effects, only for PARK_STAGES; X_park = 0.5 * share of the player's PA' with that home team.
  * Optional Tier 3 "indicator": a Statcast count that measures the same talent faster, e.g. barrels/BBE for 'hr':
        ind_y ~ Binomial(ind_n, invlogit(a_ind[t] + b_ind * theta[i, t] + nu[i]))
    The model learns b_ind and the noise, so Statcast is weighted by its actual reliability.

Non-centred parameterisation + nutpie were needed for 0 divergences: target_accept=0.9 without the
indicator (~45 s), 0.95 with it (~105 s; 0.9 gave 28 divergences). Simulated results: 80% coverage 0.83 / 0.82,
RMSE 0.0341 / 0.0328 vs 0.0387 for a regressed 3-year average. Reproduce: scripts/verify_state_space_sim.py
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

AGE_MIN, AGE_MAX = 20, 40


def _age_bucket(age) -> np.ndarray:
    return (np.clip(np.asarray(age), AGE_MIN, AGE_MAX) - AGE_MIN).astype(int)


@dataclass
class StageData:
    obs: pd.DataFrame          # one row per observed player-season (see build_stage_data)
    states: pd.DataFrame       # one row per latent (player, season)
    X_park: np.ndarray | None  # (n_obs, n_venues) or None
    venues: list               # venue ids, column order of X_park
    window_end: int


def build_stage_data(obs: pd.DataFrame, window_end: int, exposures: pd.DataFrame | None = None) -> StageData:
    """obs columns (required): mlbam_id, season, age, pa, y, n, mu_league
         pa = PA' (or BF') of that player-season (used for the talent prior), n = stage trials.
       obs columns (optional, Tier 3): ind_y, ind_n  (NaN where Statcast is missing)
       exposures (optional): mlbam_id, season, venue_id, share   (share of PA' by home venue; sums to 1)
       Rows with n == 0 are allowed (they carry no likelihood but keep the state chain intact).
    """
    obs = obs[obs.season <= window_end].sort_values(["mlbam_id", "season"]).reset_index(drop=True)
    first = obs.groupby("mlbam_id").season.min()
    age_first = obs.groupby("mlbam_id").apply(lambda d: d.age.iloc[0] - (d.season.iloc[0] - d.season.min()),
                                              include_groups=False)
    pa_first = obs.groupby("mlbam_id").pa.first().clip(lower=1)
    lz = np.log(pa_first)
    lz = (lz - lz.mean()) / lz.std()

    rows = [(pid, s) for pid, f in first.items() for s in range(int(f), window_end + 1)]
    st = pd.DataFrame(rows, columns=["mlbam_id", "season"])
    st["age"] = st.mlbam_id.map(age_first) + st.season - st.mlbam_id.map(first)
    st["is_first"] = st.season.eq(st.mlbam_id.map(first))
    st["start_idx"] = (st.index.to_series() - st.groupby("mlbam_id").cumcount()).astype(int)
    st["log_pa_first_z"] = np.where(st.is_first, st.mlbam_id.map(lz), 0.0)
    key = pd.Series(st.index.values, index=pd.MultiIndex.from_frame(st[["mlbam_id", "season"]]))
    obs["state_idx"] = key.loc[list(zip(obs.mlbam_id, obs.season))].to_numpy()

    X, venues = None, []
    if exposures is not None and len(exposures):
        venues = sorted(exposures.venue_id.unique().tolist())
        vidx = {v: j for j, v in enumerate(venues)}
        X = np.zeros((len(obs), len(venues)))
        row_of = {(p, s): r for r, (p, s) in enumerate(zip(obs.mlbam_id, obs.season))}
        for e in exposures.itertuples():
            r = row_of.get((e.mlbam_id, e.season))
            if r is not None:
                X[r, vidx[e.venue_id]] += 0.5 * e.share
    return StageData(obs=obs, states=st, X_park=X, venues=venues, window_end=window_end)


def build_model(d: StageData, use_park: bool, use_indicator: bool = False,
                innov: str = "normal", use_role: bool = False,
                obs_noise: bool = False) -> pm.Model:
    obs, st = d.obs, d.states
    n_ages = AGE_MAX - AGE_MIN + 1
    with pm.Model() as m:
        tau = pm.HalfNormal("tau", 0.3)
        sigma_pop = pm.HalfNormal("sigma_pop", 1.0)
        lam = pm.Normal("lam", 0.0, 0.5)
        sigma_age = pm.HalfNormal("sigma_age", 0.02)
        g0 = pm.Normal("g0", 0.0, 0.1)
        steps = pm.Normal("age_steps_raw", 0.0, 1.0, shape=n_ages - 1)
        g = pm.Deterministic("g_age", pt.concatenate([pt.stack([g0]), g0 + pt.cumsum(steps * sigma_age)]))

        if innov == "normal":
            e = pm.Normal("e", 0.0, 1.0, shape=len(st))
            inc = pt.switch(st.is_first.to_numpy(),
                            lam * st.log_pa_first_z.to_numpy() + sigma_pop * e,
                            g[_age_bucket(st.age)] + tau * e)
        elif innov == "t4":
            # M2a E4: heavy-tailed transitions (first-season population draw stays Normal).
            # Disjoint index sets keep the latent dimension at len(st).
            first_idx = np.flatnonzero(st.is_first.to_numpy())
            trans_idx = np.flatnonzero(~st.is_first.to_numpy())
            e1 = pm.Normal("e_first", 0.0, 1.0, shape=len(first_idx))
            et = pm.StudentT("e_trans", nu=4, mu=0.0, sigma=1.0, shape=len(trans_idx))
            inc = pt.zeros(len(st))
            inc = pt.set_subtensor(
                inc[first_idx],
                lam * st.log_pa_first_z.to_numpy()[first_idx] + sigma_pop * e1)
            inc = pt.set_subtensor(
                inc[trans_idx],
                g[_age_bucket(st.age.to_numpy()[trans_idx])] + tau * et)
        else:
            raise ValueError(f"unknown innov {innov!r}")
        C = pt.cumsum(inc)
        theta = pm.Deterministic("theta", C - pt.concatenate([pt.zeros(1), C])[st.start_idx.to_numpy()])

        logit_p = obs.mu_league.to_numpy() + theta[obs.state_idx.to_numpy()]
        if obs_noise:
            # M2b E5: transient season-level noise. Without it, every extra-binomial
            # year-to-year wiggle must live in the persistent walk (inflating tau ->
            # T-1 chasing); this term gives it a home that does not propagate.
            sigma_obs = pm.HalfNormal("sigma_obs", 0.2)
            eps = pm.Normal("eps_raw", 0.0, 1.0, shape=len(obs))
            logit_p = logit_p + sigma_obs * eps
        if use_role:
            delta_role = pm.Normal("delta_role", 0.0, 0.5)
            logit_p = logit_p + delta_role * obs.x_role.to_numpy()
        if use_park and d.X_park is not None:
            park_sd = pm.HalfNormal("park_sd", 0.1)
            phi = pm.Deterministic("phi", pm.Normal("phi_raw", 0.0, 1.0, shape=len(d.venues)) * park_sd)
            logit_p = logit_p + pt.dot(d.X_park, phi)
        has_n = obs.n.to_numpy() > 0
        pm.Binomial("y", n=obs.n.to_numpy()[has_n], logit_p=logit_p[has_n], observed=obs.y.to_numpy()[has_n])

        if use_indicator:
            ok = obs.ind_n.notna().to_numpy() & (obs.ind_n.fillna(0).to_numpy() > 0)
            sub = obs[ok]
            seasons = sorted(sub.season.unique().tolist())
            s_idx = sub.season.map({s: j for j, s in enumerate(seasons)}).to_numpy()
            p_codes, _ = pd.factorize(sub.mlbam_id)
            a_ind = pm.Normal("a_ind", -2.0, 1.5, shape=len(seasons))
            b_ind = pm.Normal("b_ind", 0.0, 2.0)
            s_nu = pm.HalfNormal("s_nu", 0.3)
            nu = pm.Normal("nu_raw", 0.0, 1.0, shape=int(p_codes.max() + 1)) * s_nu
            pm.Binomial("ind", n=sub.ind_n.astype(int).to_numpy(),
                        logit_p=a_ind[s_idx] + b_ind * theta[sub.state_idx.to_numpy()] + nu[p_codes],
                        observed=sub.ind_y.astype(int).to_numpy())
    return m


def fit(model: pm.Model, draws: int = 500, tune: int = 500, chains: int = 2, seed: int = 1,
        target_accept: float = 0.9):
    with model:
        return pm.sample(draws=draws, tune=tune, chains=chains, cores=chains, target_accept=target_accept,
                         nuts_sampler="nutpie", random_seed=seed, progressbar=False)


def project(idata, d: StageData, horizons: int, mu_proj: float, rng: np.random.Generator,
            park_exposure: dict | None = None, mu_sd: float = 0.0,
            role_x: dict | None = None, innov: str = "normal") -> tuple[pd.DataFrame, np.ndarray]:
    """Project every player who has a state at window_end.

    Returns (players, P) where players has columns mlbam_id, age_next and
    P has shape (n_players, horizons, n_draws) = talent probability for seasons window_end+1 .. +horizons.
    park_exposure: optional {mlbam_id: {venue_id: 0.5*share}} -> non-neutral projection. Default neutral.
    mu_sd: environment forecast sd; one persistent shock per posterior draw (common across
    players and horizons — league-environment error is shared, not per-player).
    role_x: optional {mlbam_id: centred covariate} paired with a fitted delta_role.
    """
    post = idata.posterior
    stack = lambda v: post[v].stack(s=("chain", "draw")).to_numpy()
    th, g, tau = stack("theta"), stack("g_age"), stack("tau")
    S = th.shape[-1]
    last = d.states[d.states.season == d.window_end]
    cur = th[last.index.to_numpy()]                      # (n_players, S)
    env_shock = mu_sd * rng.standard_normal(S) if mu_sd > 0 else 0.0
    # transient season noise (E5): part of every realized season rate, but not persistent —
    # drawn fresh per horizon and never added to the talent walk.
    obs_sd = stack("sigma_obs") if "sigma_obs" in post else None
    role_term = 0.0
    if role_x is not None and "delta_role" in post:
        delta = stack("delta_role")
        x = np.array([role_x.get(pid, 0.0) for pid in last.mlbam_id])
        role_term = x[:, None] * delta[None, :]
    P = np.empty((len(last), horizons, S))
    step_noise = (lambda: rng.standard_t(4, cur.shape)) if innov == "t4" \
        else (lambda: rng.standard_normal(cur.shape))
    for h in range(1, horizons + 1):
        cur = cur + g[_age_bucket(last.age.to_numpy() + h)] + tau * step_noise()
        logit = mu_proj + env_shock + role_term + cur
        if obs_sd is not None:
            logit = logit + obs_sd * rng.standard_normal(cur.shape)
        if park_exposure is not None and "phi" in post:
            phi = stack("phi")
            vpos = {v: j for j, v in enumerate(d.venues)}
            for r, pid in enumerate(last.mlbam_id):
                for v, x in park_exposure.get(pid, {}).items():
                    if v in vpos:
                        logit[r] += x * phi[vpos[v]]
        P[:, h - 1, :] = 1.0 / (1.0 + np.exp(-logit))
    players = pd.DataFrame({"mlbam_id": last.mlbam_id.to_numpy(), "age_next": last.age.to_numpy() + 1})
    return players, P
