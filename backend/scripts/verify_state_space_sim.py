"""Full-scale simulation check of keystone.models.state_space (runs ~2-4 min).

Simulates ~1,800 players over 2019-2025 with aging, talent drift, park effects, playing-time selection
and a Statcast-like indicator, fits on 2019-2024, projects 2025, and reports calibration + RMSE.
Usage:  python scripts/verify_state_space_sim.py [--indicator]
"""
import sys
import time

import numpy as np
import pandas as pd

from keystone.components import simulate_season  # noqa: F401  (import check)
from keystone.models import state_space as ss

USE_IND = "--indicator" in sys.argv
rng = np.random.default_rng(7)
N_PLAYERS, N_VENUES, TARGET = 1800, 30, 2025
ages = np.arange(ss.AGE_MIN, ss.AGE_MAX + 1)
true_g = np.where(ages < 27, 0.03, -0.025 * (ages - 27) / 5 - 0.01)
true_phi = rng.normal(0, 0.15, N_VENUES)
mu = {s: np.log(0.22 / 0.78) + 0.02 * (s - 2019) for s in range(2019, TARGET + 1)}

rows, expo = [], []
for i in range(N_PLAYERS):
    first = int(rng.integers(2019, 2025)); last = min(TARGET, first + int(rng.integers(0, 7)))
    age0 = int(rng.integers(22, 34)); th = rng.normal(0, 0.3); team = int(rng.integers(N_VENUES)); nu = rng.normal(0, .15)
    for s in range(first, last + 1):
        if s > first:
            th += true_g[np.clip(age0 + s - first, ss.AGE_MIN, ss.AGE_MAX) - ss.AGE_MIN] + rng.normal(0, 0.12)
        if rng.random() < 0.15:
            team = int(rng.integers(N_VENUES))
        n = int(np.clip(rng.normal(350 - 600 * th, 180), 1, 720))
        p = 1 / (1 + np.exp(-(mu[s] + th + 0.5 * true_phi[team])))
        bbe = int(n * 0.7)
        q = 1 / (1 + np.exp(-(-2.5 + 1.4 * th + nu)))
        rows.append(dict(mlbam_id=i, season=s, age=age0 + s - first, pa=n, n=n, y=rng.binomial(n, p),
                         mu_league=mu[s], ind_n=bbe, ind_y=rng.binomial(bbe, q), venue=team))
        expo.append(dict(mlbam_id=i, season=s, venue_id=team, share=1.0))
allobs, expo = pd.DataFrame(rows), pd.DataFrame(expo)
train, test = allobs[allobs.season < TARGET], allobs[allobs.season == TARGET]

d = ss.build_stage_data(train, window_end=TARGET - 1, exposures=expo[expo.season < TARGET])
print(f"obs={len(d.obs)} states={len(d.states)} indicator={USE_IND}")
t0 = time.time()
idata = ss.fit(ss.build_model(d, use_park=True, use_indicator=USE_IND), target_accept=0.95 if USE_IND else 0.9)
print(f"sampling seconds: {time.time() - t0:.0f}   divergences: {int(idata.sample_stats.diverging.sum())}")

mu_proj = np.mean([mu[s] for s in range(TARGET - 3, TARGET)])
players, P = ss.project(idata, d, horizons=1, mu_proj=mu_proj, rng=np.random.default_rng(3))
phi = idata.posterior["phi"].stack(s=("chain", "draw")).to_numpy()
vpos = {v: j for j, v in enumerate(d.venues)}
pos = {pid: r for r, pid in enumerate(players.mlbam_id)}
cov, se_m, se_b, w = [], [], [], []
r2 = np.random.default_rng(5)
for r in test[test.mlbam_id.isin(pos)].itertuples():
    pr = 1 / (1 + np.exp(-(np.log(P[pos[r.mlbam_id], 0] / (1 - P[pos[r.mlbam_id], 0])) + 0.5 * phi[vpos[r.venue]])))
    sim = r2.binomial(r.n, pr) / r.n
    lo, hi = np.quantile(sim, [.1, .9])
    cov.append(lo <= r.y / r.n <= hi)
    se_m.append((pr.mean() - r.y / r.n) ** 2)
    prev = train[train.mlbam_id == r.mlbam_id].tail(3)
    se_b.append(((prev.y.sum() + 0.22 * 200) / (prev.n.sum() + 200) - r.y / r.n) ** 2)
    w.append(r.n)
print(f"test players={len(cov)}  80% coverage={np.mean(cov):.3f}  (target 0.75-0.85)")
print(f"PA-weighted RMSE  model={np.sqrt(np.average(se_m, weights=w)):.4f}  regressed-avg baseline={np.sqrt(np.average(se_b, weights=w)):.4f}")
