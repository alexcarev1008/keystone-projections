"""Fast smoke test (~1 min). The full-scale calibration check is scripts/verify_state_space_sim.py."""
import numpy as np
import pandas as pd

from keystone.models import state_space as ss


def _sim(n_players=250, seasons=range(2019, 2025), seed=0):
    rng = np.random.default_rng(seed)
    mu = np.log(0.22 / 0.78)
    rows, expo = [], []
    for i in range(n_players):
        first = int(rng.integers(2019, 2025)); age = int(rng.integers(22, 34)); th = rng.normal(0, .3)
        venue = int(rng.integers(5))
        for s in range(first, 2025):
            if s > first:
                th += rng.normal(0, .12)
            n = int(rng.integers(50, 650))
            y = rng.binomial(n, 1 / (1 + np.exp(-(mu + th))))
            rows.append(dict(mlbam_id=i, season=s, age=age + s - first, pa=n, n=n, y=y, mu_league=mu))
            expo.append(dict(mlbam_id=i, season=s, venue_id=100 + venue, share=1.0))
    return pd.DataFrame(rows), pd.DataFrame(expo)


def test_fit_and_project_shapes():
    obs, expo = _sim()
    d = ss.build_stage_data(obs, window_end=2024, exposures=expo)
    assert d.states.groupby("mlbam_id").season.max().eq(2024).all()
    m = ss.build_model(d, use_park=True)
    idata = ss.fit(m, draws=150, tune=150, chains=2)
    assert int(idata.sample_stats.diverging.sum()) < 10
    players, P = ss.project(idata, d, horizons=4, mu_proj=float(obs.mu_league.iloc[0]),
                            rng=np.random.default_rng(1))
    assert P.shape == (obs.mlbam_id.nunique(), 4, 300)
    assert np.all((P > 0) & (P < 1))
    # uncertainty must widen with horizon
    width = np.quantile(P, .9, axis=2) - np.quantile(P, .1, axis=2)
    assert (width[:, 3] > width[:, 0]).mean() > 0.9
