import numpy as np
import pandas as pd
import pytest

from keystone.models import playing_time as PT


def _ps(rows):
    df = pd.DataFrame(rows)
    for c in ["plateAppearances", "outs", "gamesStarted", "gamesPitched"]:
        if c not in df:
            df[c] = 0
    return df


def test_population_and_outcome_fill():
    ps = _ps([dict(mlbam_id=1, season=2022, age=27, plateAppearances=500),
              dict(mlbam_id=2, season=2021, age=30, plateAppearances=300),
              dict(mlbam_id=3, season=2019, age=25, plateAppearances=600),
              dict(mlbam_id=1, season=2023, age=28, plateAppearances=450)])
    t = PT.build_pt_table(ps, "H", 2023)
    assert set(t.mlbam_id) == {1, 2}          # 3 is outside T-1/T-2
    r2 = t.set_index("mlbam_id").loc[2]
    assert r2.pt_actual == 0 and r2.played == 0
    assert r2.played1 == 0 and r2.played2 == 1
    assert r2["drop"] == pytest.approx(np.sqrt(300) / 10)
    r1 = t.set_index("mlbam_id").loc[1]
    assert r1.pt_actual == 450 and r1.agec == pytest.approx((28 - 29) / 5)


def test_2020_feature_scaling():
    ps = _ps([dict(mlbam_id=1, season=2020, age=27, plateAppearances=200),
              dict(mlbam_id=1, season=2021, age=28, plateAppearances=500)])
    t = PT.build_pt_table(ps, "H", 2022).set_index("mlbam_id")
    assert t.loc[1, "s2"] == pytest.approx(np.sqrt(200 * 162 / 60) / 10)


def test_training_table_leakage_and_2020_outcome_dropped():
    rows = [dict(mlbam_id=i, season=s, age=25 + s - 2016, plateAppearances=400 + i)
            for i in range(20) for s in range(2016, 2024)]
    ps = _ps(rows)
    tr = PT.training_table(ps, "H", 2023)
    assert 2020 not in set(tr.target)
    assert tr.target.max() == 2022
    tr2 = PT.training_table(ps[ps.season < 2023], "H", 2023)
    pd.testing.assert_frame_equal(tr, tr2)     # rows at/after target change nothing


def test_predict_hurdle_math():
    fit = PT.PTFit(role="H", beta=np.zeros((1, 8)), gamma=np.full((1, 8), 0.0),
                   sigma=np.array([0.5]), features=PT.FEATURES["H"])
    fit.gamma[0, 0] = 2.0                      # mu = 2 via const
    table = pd.DataFrame({f: [0.0] for f in PT.FEATURES["H"]})
    table["const"] = 1.0
    table["mlbam_id"] = 1
    out = PT.predict(fit, table)
    assert out.p_play[0] == pytest.approx(0.5)
    assert out.pt_expected[0] == pytest.approx(0.5 * 100 * (4 + 0.25))


def test_simulate_horizons_rolls_and_decays():
    beta = np.zeros((1, 8)); beta[0, 0] = 0.0  # p_play = .5 each year
    gamma = np.zeros((1, 8)); gamma[0, 0] = 2.0
    fit = PT.PTFit(role="H", beta=beta, gamma=gamma, sigma=np.array([1e-9]),
                   features=PT.FEATURES["H"])
    table = pd.DataFrame({f: [0.0] for f in PT.FEATURES["H"]})
    table["const"] = 1.0
    table["mlbam_id"] = 7
    np.random.seed(0)
    sim = PT.simulate_horizons(fit, table, horizons=4, seed=3)
    assert list(sim.horizon) == [1, 2, 3, 4]
    assert set(sim.mlbam_id) == {7}
    assert (sim.p_play <= 1).all() and (sim.pt_expected >= 0).all()
    assert (sim.p_regular <= sim.p_play + 1e-12).all()


def _guts():
    return pd.DataFrame({"season": [2020, 2021, 2022], "wOBA": 0.310, "wOBAScale": 1.24,
                         "wBB": 0.69, "wHBP": 0.72, "w1B": 0.88, "w2B": 1.25,
                         "w3B": 1.59, "wHR": 2.05, "cFIP": 3.15})


def test_talent_sign_and_shrinkage():
    base = dict(atBats=500, hits=125, doubles=25, triples=2, homeRuns=15, baseOnBalls=50,
                intentionalWalks=0, hitByPitch=5, sacFlies=5, strikeOuts=100)
    star = dict(base, hits=175, homeRuns=40)
    ps = _ps([dict(mlbam_id=1, season=2021, age=27, plateAppearances=560, **base),
              dict(mlbam_id=2, season=2021, age=27, plateAppearances=560, **star)])
    t = PT.build_pt_table(ps, "H", 2022, talent=True, guts=_guts()).set_index("mlbam_id")
    assert t.loc[2, "talent"] > t.loc[1, "talent"]
    # ballast shrinks: |scaled talent| < |raw dev| / TALENT_SCALE
    tt = PT.talent_table(ps, "H", _guts()).set_index("mlbam_id")
    assert abs(t.loc[2, "talent"]) < abs(tt.loc[2, "dev"]) / PT.TALENT_SCALE["H"]


def test_talent_leakage_guard():
    base = dict(atBats=500, hits=140, doubles=25, triples=2, homeRuns=20, baseOnBalls=50,
                intentionalWalks=0, hitByPitch=5, sacFlies=5, strikeOuts=100)
    great = dict(base, hits=200, homeRuns=50)
    ps = _ps([dict(mlbam_id=1, season=2021, age=27, plateAppearances=560, **base),
              dict(mlbam_id=1, season=2022, age=28, plateAppearances=560, **great)])
    with_t = PT.build_pt_table(ps, "H", 2022, talent=True, guts=_guts())
    without_t = PT.build_pt_table(ps[ps.season < 2022], "H", 2022, talent=True, guts=_guts())
    pd.testing.assert_series_equal(with_t.talent, without_t.talent)


def test_fit_recovers_signal():
    rng = np.random.default_rng(5)
    n = 400
    s1 = rng.uniform(0, 2.5, n)
    p = 1 / (1 + np.exp(-(-1.0 + 2.0 * s1)))
    z = rng.random(n) < p
    y = np.where(z, np.maximum(0.3 + 0.8 * s1 + 0.1 * rng.standard_normal(n), 0.05), 0.0)
    tr = pd.DataFrame({"const": 1.0, "s1": s1, "s2": 0.0, "played1": 1.0, "played2": 1.0,
                       "agec": 0.0, "agec2": 0.0, "drop": 0.0,
                       "pt_actual": (y * 10) ** 2, "played": z.astype(float)})
    fit = PT.fit_pt(tr, "H", draws=150, tune=150, chains=2, seed=2)
    assert fit.beta[:, 1].mean() > 0.5         # s1 raises play prob
    assert fit.gamma[:, 1].mean() > 0.3        # s1 raises conditional PT
