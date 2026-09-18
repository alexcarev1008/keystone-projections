"""M3 playing-time hurdle model (docs/fable/M3_playing_time.md).

played ~ Bernoulli(invlogit(X beta));  sqrt(pt)/scale | played ~ Normal(X gamma, sigma).
E[pt] = p_play * scale^2 * (mu^2 + sigma^2). Features use seasons <= T-1 only; 2020 PT is
scaled by 162/60 as a feature and dropped as a training outcome. Backtested against
marcel_playing_time on the same population (any PT in T-1 or T-2, actual = 0 if absent).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pymc as pm

SCALE = {"H": 10.0, "P": 5.0}
SHORT_2020 = 162.0 / 60.0
FEATURES = {"H": ["const", "s1", "s2", "played1", "played2", "agec", "agec2", "drop"],
            "P": ["const", "s1", "s2", "played1", "played2", "agec", "agec2", "drop", "sp_share"]}
REGULAR_PT = {"H": 300.0, "P": 100.0}


def pt_series(ps: pd.DataFrame, role: str) -> pd.DataFrame:
    """Per (mlbam_id, season): pt (PA or IP), sp_share, age."""
    out = ps[["mlbam_id", "season", "age"]].copy()
    if role == "H":
        out["pt"] = ps.plateAppearances.astype(float)
        out["sp_share"] = 0.0
    else:
        out["pt"] = (ps.outs / 3.0).astype(float)
        out["sp_share"] = (ps.gamesStarted / ps.gamesPitched.where(ps.gamesPitched > 0)).fillna(0.0)
    return out


def _adj(pt: pd.Series, season: int) -> pd.Series:
    return pt * SHORT_2020 if season == 2020 else pt


def build_pt_table(ps: pd.DataFrame, role: str, target: int) -> pd.DataFrame:
    """Population = any PT in target-1 or target-2. Features from < target; outcome = PT at target (0 if absent)."""
    t = pt_series(ps, role)
    y1 = t[t.season == target - 1].set_index("mlbam_id")
    y2 = t[t.season == target - 2].set_index("mlbam_id")
    ids = y1[y1.pt > 0].index.union(y2[y2.pt > 0].index)
    scale = SCALE[role]
    pt1 = _adj(y1.pt.reindex(ids).fillna(0.0), target - 1)
    pt2 = _adj(y2.pt.reindex(ids).fillna(0.0), target - 2)
    s1, s2 = np.sqrt(pt1) / scale, np.sqrt(pt2) / scale
    age1 = y1.age.reindex(ids)
    age2 = y2.age.reindex(ids)
    age = age1.fillna(age2 + 1) + 1  # age at target
    agec = (age - 29.0) / 5.0
    X = pd.DataFrame({"const": 1.0, "s1": s1, "s2": s2,
                      "played1": (pt1 > 0).astype(float), "played2": (pt2 > 0).astype(float),
                      "agec": agec, "agec2": agec ** 2,
                      "drop": np.maximum(0.0, s2 - s1)}, index=ids)
    if role == "P":
        X["sp_share"] = y1.sp_share.reindex(ids).fillna(0.0)
    actual = t[t.season == target].set_index("mlbam_id").pt.reindex(ids).fillna(0.0)
    X["pt_actual"] = actual
    X["played"] = (actual > 0).astype(float)
    X["target"] = target
    return X.reset_index().rename(columns={"index": "mlbam_id"})


def training_table(ps: pd.DataFrame, role: str, target: int, first_outcome: int = 2017) -> pd.DataFrame:
    """Outcome seasons first_outcome..target-1, skipping 2020. Leakage: only rows with season < target used."""
    ps = ps[ps.season < target]
    parts = [build_pt_table(ps, role, s) for s in range(first_outcome, target) if s != 2020]
    return pd.concat(parts, ignore_index=True)


@dataclass
class PTFit:
    role: str
    beta: np.ndarray    # (draws, k) hurdle coefficients
    gamma: np.ndarray   # (draws, k) conditional coefficients
    sigma: np.ndarray   # (draws,)
    features: list


def fit_pt(train: pd.DataFrame, role: str, draws: int = 500, tune: int = 500,
           chains: int = 2, seed: int = 1) -> PTFit:
    feats = FEATURES[role]
    X = train[feats].to_numpy(dtype=float)
    played = train.played.to_numpy()
    pos = train.pt_actual.to_numpy() > 0
    Xp = X[pos]
    y = np.sqrt(train.pt_actual.to_numpy()[pos]) / SCALE[role]
    with pm.Model():
        beta = pm.Normal("beta", 0.0, 1.5, shape=X.shape[1])
        gamma = pm.Normal("gamma", 0.0, 1.5, shape=X.shape[1])
        sigma = pm.HalfNormal("sigma", 1.0)
        pm.Bernoulli("z", p=pm.math.invlogit(X @ beta), observed=played)
        pm.Normal("y", mu=Xp @ gamma, sigma=sigma, observed=y)
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=chains,
                          nuts_sampler="nutpie", random_seed=seed, progressbar=False)
    post = idata.posterior
    return PTFit(role=role,
                 beta=post.beta.to_numpy().reshape(-1, X.shape[1]),
                 gamma=post.gamma.to_numpy().reshape(-1, X.shape[1]),
                 sigma=post.sigma.to_numpy().reshape(-1),
                 features=feats)


def predict(fit: PTFit, table: pd.DataFrame) -> pd.DataFrame:
    """Posterior-mean p_play, conditional E[pt], expected pt per player."""
    X = table[fit.features].to_numpy(dtype=float)
    logit = X @ fit.beta.T                       # (n, draws)
    p = 1.0 / (1.0 + np.exp(-logit))
    mu = X @ fit.gamma.T
    s2 = SCALE[fit.role] ** 2
    e_cond = s2 * (mu ** 2 + fit.sigma[None, :] ** 2)
    return pd.DataFrame({"mlbam_id": table.mlbam_id.to_numpy(),
                         "p_play": p.mean(1),
                         "pt_cond": (p * e_cond).mean(1) / np.maximum(p.mean(1), 1e-9),
                         "pt_expected": (p * e_cond).mean(1)})


def simulate_horizons(fit: PTFit, table: pd.DataFrame, horizons: int = 4,
                      seed: int = 1) -> pd.DataFrame:
    """Posterior simulation h=1..horizons; rolls features forward. Returns one row per (mlbam_id, horizon)."""
    rng = np.random.default_rng(seed)
    feats = fit.features
    n, nd = len(table), fit.beta.shape[0]
    col = {f: i for i, f in enumerate(feats)}
    X = np.repeat(table[feats].to_numpy(dtype=float)[:, None, :], nd, axis=1)  # (n, draws, k)
    scale = SCALE[fit.role]
    rows = []
    for h in range(1, horizons + 1):
        logit = np.einsum("ndk,dk->nd", X, fit.beta)
        p = 1.0 / (1.0 + np.exp(-logit))
        z = rng.random((n, nd)) < p
        mu = np.einsum("ndk,dk->nd", X, fit.gamma)
        sq = np.maximum(mu + fit.sigma[None, :] * rng.standard_normal((n, nd)), 0.0)
        pt = np.where(z, (sq * scale) ** 2, 0.0)
        rows.append(pd.DataFrame({"mlbam_id": table.mlbam_id.to_numpy(), "horizon": h,
                                  "p_play": z.mean(1), "pt_expected": pt.mean(1),
                                  "p_regular": (pt >= REGULAR_PT[fit.role]).mean(1)}))
        s_new = np.sqrt(pt) / scale
        X[:, :, col["s2"]] = X[:, :, col["s1"]]
        X[:, :, col["played2"]] = X[:, :, col["played1"]]
        X[:, :, col["drop"]] = np.maximum(0.0, X[:, :, col["s1"]] - s_new)
        X[:, :, col["s1"]] = s_new
        X[:, :, col["played1"]] = z.astype(float)
        X[:, :, col["agec"]] += 1.0 / 5.0
        X[:, :, col["agec2"]] = X[:, :, col["agec"]] ** 2
    return pd.concat(rows, ignore_index=True)


def backtest_pt(ps_by_role: dict, targets: tuple, seed: int = 1) -> pd.DataFrame:
    """Rolling-origin comparison vs marcel_playing_time. Population and actuals per build_pt_table."""
    from keystone.models.marcel import marcel_playing_time
    out = []
    for role, ps in ps_by_role.items():
        for target in targets:
            train = training_table(ps, role, target)
            fit = fit_pt(train, role, seed=seed)
            ev = build_pt_table(ps[ps.season <= target], role, target)
            pred = predict(fit, ev).set_index("mlbam_id")
            m_pt = marcel_playing_time(ps[ps.season < target], role, target)
            ids = ev.set_index("mlbam_id").index
            actual = ev.set_index("mlbam_id").pt_actual
            played = ev.set_index("mlbam_id").played
            base_rate = train.played.mean()
            for name, est in [("marcel", m_pt.reindex(ids)), ("hurdle", pred.pt_expected)]:
                err = est - actual
                out.append(dict(role=role, target=target, model=name, n=len(ids),
                                rmse=float(np.sqrt((err ** 2).mean())), mae=float(err.abs().mean()),
                                bias=float(err.mean())))
            out[-1]["brier"] = float(((pred.p_play - played) ** 2).mean())
            out[-1]["brier_base"] = float(((base_rate - played) ** 2).mean())
    return pd.DataFrame(out)
