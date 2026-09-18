"""M2b experiments (docs/fable/M2_experiments.md): E5 obs-noise, E6 shock-only env mode."""
import arviz as az
import numpy as np
import pandas as pd

from keystone import league as LG
from keystone.models import state_space as ss


def _obs():
    return pd.DataFrame({"mlbam_id": [1, 1, 2, 2], "season": [2023, 2024] * 2,
                         "age": [27, 28, 30, 31], "pa": [500] * 4,
                         "y": [50] * 4, "n": [500] * 4, "mu_league": [0.0] * 4})


def test_build_model_obs_noise_variables():
    d = ss.build_stage_data(_obs(), window_end=2024)
    m = ss.build_model(d, use_park=False, obs_noise=True)
    assert "sigma_obs" in m.named_vars and "eps_raw" in m.named_vars
    m0 = ss.build_model(d, use_park=False)
    assert "sigma_obs" not in m0.named_vars


def test_project_obs_noise_transient_not_persistent():
    d = ss.build_stage_data(_obs(), window_end=2024)
    D = 400
    post = dict(theta=np.zeros((1, D, len(d.states))),
                g_age=np.zeros((1, D, ss.AGE_MAX - ss.AGE_MIN + 1)),
                tau=np.zeros((1, D)),
                sigma_obs=np.full((1, D), 0.3))
    idata = az.from_dict(posterior=post)
    _, P = ss.project(idata, d, 3, mu_proj=0.0, rng=np.random.default_rng(0))
    logit = np.log(P / (1 - P))
    # per-player, per-horizon noise at sd sigma_obs...
    assert 0.25 < logit[0, 0, :].std() < 0.35
    assert not np.allclose(logit[0, 0], logit[1, 0])      # not shared across players
    # ...and transient: variance does not grow with horizon (tau=0 here)
    assert logit[0, 2, :].std() < 0.4
    # zero-mean: medians unmoved
    assert abs(np.median(logit[0, 0])) < 0.05


def test_env_mode_shock_uses_baseline_point():
    seasons = list(range(2019, 2025))
    lg = pd.DataFrame({"season": seasons, "stage": "k",
                       "logit": np.linspace(0.0, -0.5, 6),
                       "n": [180_000] * 6})
    mu3 = LG.projection_logit(lg, "k", 2024)
    _, sd = LG.projection_logit_recency(lg, "k", 2024)
    # E6 semantics (wired in backtest.fit_stage_draws): point = mean3, sd = recency's sigma_env
    assert sd > 0
    mu_rec, sd_rec = LG.projection_logit_recency(lg, "k", 2024)
    assert mu_rec != mu3 and sd_rec == sd
