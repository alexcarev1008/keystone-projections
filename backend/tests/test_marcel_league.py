import numpy as np
import pandas as pd

from keystone.components import derive_pitcher
from keystone.league import pitcher_constants, projection_logit, stage_league_rates
from keystone.models.marcel import events_table, marcel, marcel_playing_time


def _hitter(pid, season, pa, k, bb=50, hr=20, hits=140, d2=25, d3=2):
    ab = pa - bb - 5 - 5
    return dict(mlbam_id=pid, season=season, plateAppearances=pa, atBats=ab, hits=hits, doubles=d2, triples=d3,
                homeRuns=hr, baseOnBalls=bb, intentionalWalks=0, hitByPitch=5, sacFlies=5, sacBunts=0,
                catchersInterference=0, strikeOuts=k)


def test_marcel_hand_calc_and_league_average_fixed_point():
    rows = []
    for s in (2022, 2023, 2024):
        rows.append(_hitter(1, s, 600, 150))        # league-average clone
        rows.append(_hitter(2, s, 600, 90))         # low-K hitter
    df = pd.DataFrame(rows)
    ev = events_table(df, "H")
    ages = pd.Series({1: 29, 2: 29})
    out = marcel(ev, "H", 2025, ages).set_index("mlbam_id")
    lg_k = 240 / 1200
    # player 2 hand calc: weighted K = 12*90, weighted PA = 12*600, regression 1200 PA at league rate
    exp_k2 = (12 * 90 + 1200 * lg_k) / (12 * 600 + 1200)
    assert np.isclose(out.loc[2, "k"], exp_k2)
    assert np.isclose(out.loc[1, "k"], (12 * 150 + 1200 * lg_k) / (12 * 600 + 1200))
    # age adjustment direction: a 25-year-old strikes out less than the same line at 29
    young = marcel(ev, "H", 2025, pd.Series({1: 25, 2: 25})).set_index("mlbam_id")
    assert young.loc[2, "k"] < out.loc[2, "k"] and young.loc[2, "hr"] > out.loc[2, "hr"]
    pt = marcel_playing_time(df, "H", 2025)
    assert np.isclose(pt.loc[1], 0.5 * 600 + 0.1 * 600 + 200)


def test_league_fip_equals_league_era():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        bf = int(rng.integers(100, 800))
        k, bb, ibb, hbp, hr = int(bf * .22), int(bf * .08), 2, int(bf * .01), int(bf * .03)
        h = int(bf * .21)
        rows.append(dict(mlbam_id=i, season=2024, battersFaced=bf, intentionalWalks=ibb, sacBunts=1,
                         catchersInterference=0, baseOnBalls=bb, hitBatsmen=hbp, hits=h, homeRuns=hr,
                         strikeOuts=k, outs=int(bf * .70), earnedRuns=int(bf * .11), gamesStarted=0, gamesPitched=30))
    pit = pd.DataFrame(rows)
    c = pitcher_constants(pit).iloc[0]
    lg = stage_league_rates(pit, "P")
    p = {r.stage: np.array([r.rate]) for r in lg.itertuples()}
    fip = derive_pitcher(p, kappa=c.kappa, c_fip=c.c_fip)["fip"][0]
    assert np.isclose(fip, c.lg_era)
    assert np.isfinite(projection_logit(lg, "k", 2024, 3))
