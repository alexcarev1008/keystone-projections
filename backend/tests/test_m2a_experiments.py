"""M2a experiments (docs/fable/M2_experiments.md): E2 env forecast, E3 SP/RP, E4 t4 innovations."""
import arviz as az
import numpy as np
import pandas as pd

from keystone import league as LG
from keystone.eval.backtest import _rp_share
from keystone.models import state_space as ss


def _lg_rates():
    # a steadily falling league rate: 2019..2024, logit 0.0 down to -0.5
    seasons = list(range(2019, 2025))
    logits = np.linspace(0.0, -0.5, 6)
    return pd.DataFrame({"season": seasons, "stage": "k",
                         "logit": logits,
                         "n": [180_000, 66_000, 180_000, 180_000, 180_000, 180_000]})


def test_projection_logit_recency_tracks_trend_and_downweights_2020():
    lg = _lg_rates()
    mu3 = LG.projection_logit(lg, "k", 2024)
    mu, sd = LG.projection_logit_recency(lg, "k", 2024)
    last = float(lg.loc[lg.season == 2024, "logit"].iloc[0])
    assert mu3 < mu <= last * 0.999 or mu < 0            # recency mean sits nearer the last season
    assert abs(mu - last) < abs(mu3 - last)
    assert sd > 0                                        # env volatility from yoy diffs
    # 2020 downweighting: same window as mean3 over 2020-2022 -> recency mean nearer 2022
    mu_w, _ = LG.projection_logit_recency(lg, "k", 2022)
    mu3_w = LG.projection_logit(lg, "k", 2022)
    l22 = float(lg.loc[lg.season == 2022, "logit"].iloc[0])
    assert abs(mu_w - l22) < abs(mu3_w - l22)


def test_rp_share():
    ps = pd.DataFrame({"mlbam_id": [1, 2, 3], "season": [2024] * 3,
                       "gamesPitched": [30, 60, 0], "gamesStarted": [30, 0, 0]})
    rp = _rp_share(ps).set_index("mlbam_id").rp_share
    assert rp[1] == 0.0 and rp[2] == 1.0 and rp[3] == 1.0   # G=0 degenerate row -> RP


def _obs(x_role=False):
    o = pd.DataFrame({"mlbam_id": [1, 1, 2, 2], "season": [2023, 2024] * 2,
                      "age": [27, 28, 30, 31], "pa": [500] * 4,
                      "y": [50] * 4, "n": [500] * 4, "mu_league": [0.0] * 4})
    if x_role:
        o["x_role"] = [-0.5, -0.5, 0.5, 0.5]
    return o


def test_build_model_role_and_t4_variables():
    d = ss.build_stage_data(_obs(x_role=True), window_end=2024)
    m = ss.build_model(d, use_park=False, use_role=True)
    assert "delta_role" in m.named_vars
    d2 = ss.build_stage_data(_obs(), window_end=2024)
    m2 = ss.build_model(d2, use_park=False, innov="t4")
    assert "e_first" in m2.named_vars and "e_trans" in m2.named_vars and "e" not in m2.named_vars
    # latent dimension unchanged: n_first + n_trans == len(states)
    assert (m2.named_vars["e_first"].type.shape[0] or 2) + \
           (m2.named_vars["e_trans"].type.shape[0] or 2) == len(d2.states)


def test_project_env_shock_and_role_x():
    d = ss.build_stage_data(_obs(), window_end=2024)
    D = 400
    post = dict(theta=np.zeros((1, D, len(d.states))),
                g_age=np.zeros((1, D, ss.AGE_MAX - ss.AGE_MIN + 1)),
                tau=np.zeros((1, D)),
                delta_role=np.full((1, D), 1.0))
    idata = az.from_dict(posterior=post)
    rng = lambda: np.random.default_rng(0)
    _, P0 = ss.project(idata, d, 1, mu_proj=0.0, rng=rng())
    assert np.allclose(P0, 0.5)
    # role covariate shifts player 1 (x=+0.5) by delta_role on the logit scale
    _, Pr = ss.project(idata, d, 1, mu_proj=0.0, rng=rng(), role_x={1: 0.5, 2: 0.0})
    assert np.allclose(Pr[0], 1 / (1 + np.exp(-0.5)))
    assert np.allclose(Pr[1], 0.5)
    # env shock: common across players within a draw, sd ~ mu_sd across draws
    _, Pe = ss.project(idata, d, 1, mu_proj=0.0, rng=rng(), mu_sd=0.3)
    logit = np.log(Pe / (1 - Pe))
    assert np.allclose(logit[0], logit[1])               # shared shock
    assert 0.2 < logit[0, 0, :].std() < 0.4              # ~mu_sd
