"""M1 fix: backtest scores park stages with the player's T-1 park exposure (leakage-safe)."""
import arviz as az
import numpy as np
import pandas as pd

from keystone.eval.backtest import park_exposure_map
from keystone.models import state_space as ss


def test_park_exposure_map_uses_only_window_end():
    exp = pd.DataFrame({"mlbam_id": [1, 1, 2, 3],
                        "season":   [2024, 2023, 2024, 2023],
                        "venue_id": [100, 101, 101, 100],
                        "share":    [1.0, 1.0, 1.0, 1.0]})
    m = park_exposure_map(exp, window_end=2024)
    assert m == {1: {100: 0.5}, 2: {101: 0.5}}          # 0.5 * share; player 3 (no T-1) absent
    assert park_exposure_map(None, 2024) == {}
    assert park_exposure_map(exp.iloc[0:0], 2024) == {}


def _fixture():
    obs = pd.DataFrame({"mlbam_id": [1, 1, 2, 2], "season": [2023, 2024] * 2,
                        "age": [27, 28, 30, 31], "pa": [500] * 4,
                        "y": [50] * 4, "n": [500] * 4, "mu_league": [0.0] * 4})
    exp = pd.DataFrame({"mlbam_id": [1, 2], "season": [2024, 2024],
                        "venue_id": [100, 101], "share": [1.0, 1.0]})
    d = ss.build_stage_data(obs, window_end=2024, exposures=exp)
    D = 30
    post = dict(theta=np.zeros((1, D, len(d.states))),
                g_age=np.zeros((1, D, ss.AGE_MAX - ss.AGE_MIN + 1)),
                tau=np.zeros((1, D)),
                phi=np.tile(np.array([0.4, -0.4]), (1, D, 1)))
    return az.from_dict(posterior=post), d


def test_project_applies_park_exposure():
    idata, d = _fixture()
    rng = lambda: np.random.default_rng(0)
    _, P_neutral = ss.project(idata, d, 1, mu_proj=0.0, rng=rng())
    _, P_aware = ss.project(idata, d, 1, mu_proj=0.0, rng=rng(),
                            park_exposure={1: {100: 0.5}})
    assert np.allclose(P_neutral, 0.5)                   # tau=0, theta=0, g=0
    expect = 1 / (1 + np.exp(-0.5 * 0.4))                # x * phi[100] on the logit scale
    assert np.allclose(P_aware[0], expect)
    assert np.allclose(P_aware[1], 0.5)                  # no exposure entry -> neutral
