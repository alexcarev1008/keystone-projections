import numpy as np
import pandas as pd

from keystone.components import derive_hitter, derive_pitcher, simulate_season, stage_counts

W = dict(wBB=0.69, wHBP=0.72, w1B=0.88, w2B=1.25, w3B=1.58, wHR=2.03)  # test-only numbers

HIT = pd.DataFrame([dict(mlbam_id=1, season=2024, plateAppearances=700, atBats=570, hits=170, doubles=30,
                         triples=2, homeRuns=40, baseOnBalls=115, intentionalWalks=10, hitByPitch=6,
                         sacFlies=5, sacBunts=0, catchersInterference=4, strikeOuts=120)])
PIT = pd.DataFrame([dict(mlbam_id=2, season=2024, battersFaced=800, baseOnBalls=50, intentionalWalks=3,
                         hitBatsmen=7, strikeOuts=220, sacBunts=2, catchersInterference=1, hits=160,
                         homeRuns=22, outs=585, sacFlies=4)])


def _rates(long):
    return {r.stage: np.array([r.y / r.n]) for r in long.itertuples()}


def test_stage_identities_hitter():
    h = HIT.iloc[0]
    long = stage_counts(HIT, "H")
    p = _rates(long)
    pa_prime = h.plateAppearances - h.intentionalWalks - h.sacBunts - h.catchersInterference
    assert pa_prime == h.atBats + (h.baseOnBalls - h.intentionalWalks) + h.hitByPitch + h.sacFlies
    babip = (h.hits - h.homeRuns) / (h.atBats - h.strikeOuts - h.homeRuns + h.sacFlies)
    assert np.isclose(p["hit_bip"][0], babip)
    singles = h.hits - h.doubles - h.triples - h.homeRuns
    woba = (W["wBB"] * (h.baseOnBalls - h.intentionalWalks) + W["wHBP"] * h.hitByPitch + W["w1B"] * singles
            + W["w2B"] * h.doubles + W["w3B"] * h.triples + W["wHR"] * h.homeRuns) / pa_prime
    d = derive_hitter(p, W, sf_rate=h.sacFlies / pa_prime)
    assert np.isclose(d["woba"][0], woba)
    assert np.isclose(d["avg"][0], h.hits / h.atBats)
    tb = singles + 2 * h.doubles + 3 * h.triples + 4 * h.homeRuns
    assert np.isclose(d["slg"][0], tb / h.atBats)


def test_stage_identities_pitcher():
    q = PIT.iloc[0]
    long = stage_counts(PIT, "P")
    p = _rates(long)
    bf_prime = q.battersFaced - q.intentionalWalks - q.sacBunts - q.catchersInterference
    ubb = q.baseOnBalls - q.intentionalWalks
    kappa = q.outs / (bf_prime - ubb - q.hitBatsmen - q.hits)
    d = derive_pitcher(p, kappa=kappa, c_fip=3.1)
    ip = q.outs / 3
    fip = (13 * q.homeRuns + 3 * (ubb + q.hitBatsmen) - 2 * q.strikeOuts) / ip + 3.1
    assert np.isclose(d["fip"][0], fip)
    assert np.isclose(d["ip_per_bf"][0] * bf_prime, ip)


def test_simulated_counts_are_coherent():
    rng = np.random.default_rng(0)
    p = {s: np.full(2000, v) for s, v in dict(k=.22, bb=.09, hbp=.012, hr=.045, hit_bip=.29, xbh=.3, triple=.08).items()}
    sim = simulate_season(p, 600, rng)
    total = sim["k"] + sim["bb"] + sim["hbp"] + sim["hr"] + sim["h_bip"]
    assert (total <= 600).all() and (sim["single"] >= 0).all() and (sim["double"] >= 0).all()
    assert abs(sim["k"].mean() / 600 - .22) < .005
