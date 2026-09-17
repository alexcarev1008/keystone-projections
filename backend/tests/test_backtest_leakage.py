"""The no-leakage guarantee of MANUAL.md §6.2, asserted three ways on tiny synthetic data.

1. `train_slice` removes every row at or after the target season from every table.
2. The observations handed to the state-space model contain no season >= target.
3. End to end: perturbing season-T counts beyond recognition changes no projection — not
   Marcel's, not the baselines', and not the state-space model's.

Sampling here is deliberately tiny (1 chain, 40 draws) — this test checks data flow, not fit
quality. `scripts/verify_state_space_sim.py` is what checks the model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from keystone.eval import backtest as BT

TARGET = 2024
SEASONS = list(range(TARGET - 6, TARGET + 1))
TINY = dict(draws=40, tune=40, chains=1)


def _player_seasons(n_players: int = 40, seed: int = 0) -> pd.DataFrame:
    """Stats API-shaped hitter seasons: every player plays every season."""
    rng = np.random.default_rng(seed)
    talent = rng.normal(0, 0.25, n_players)
    rows = []
    for i in range(n_players):
        for s in SEASONS:
            pa = int(rng.integers(420, 650))
            k = int(pa * (1 / (1 + np.exp(-(-1.2 + talent[i])))))
            bb = int((pa - k) * 0.09)
            hbp = int((pa - k - bb) * 0.01)
            hr = int((pa - k - bb - hbp) * 0.045)
            h_bip = int((pa - k - bb - hbp - hr) * 0.30)
            doubles, triples = int(h_bip * 0.22), int(h_bip * 0.02)
            rows.append(dict(mlbam_id=1000 + i, season=s, plateAppearances=pa,
                             intentionalWalks=0, sacBunts=0, catchersInterference=0, sacFlies=4,
                             strikeOuts=k, baseOnBalls=bb, hitByPitch=hbp, homeRuns=hr,
                             hits=h_bip + hr, doubles=doubles, triples=triples,
                             age=26 + (s - SEASONS[0]), primary_pos="OF",
                             birth_date=f"{s - 26 - (s - SEASONS[0])}-05-01",
                             team_abbr="AAA", main_team_id=1, num_teams=1, outs=0))
    return pd.DataFrame(rows)


def _bundle(ps_h: pd.DataFrame) -> BT.Bundle:
    from keystone.league import hitter_constants, stage_league_rates

    lg_h = stage_league_rates(ps_h, "H").merge(hitter_constants(ps_h), on="season", how="left")
    empty_p = ps_h.head(0)
    guts = pd.DataFrame({"season": SEASONS, "wBB": 0.69, "wHBP": 0.72, "w1B": 0.88,
                         "w2B": 1.25, "w3B": 1.58, "wHR": 2.02})
    people = (ps_h[["mlbam_id", "birth_date"]].drop_duplicates("mlbam_id")
              .assign(birth_date="1996-05-01"))
    exp = pd.DataFrame({"mlbam_id": ps_h.mlbam_id, "season": ps_h.season,
                        "venue_id": 1, "share": 1.0}).drop_duplicates()
    return BT.Bundle(ps={"H": ps_h, "P": empty_p}, exp={"H": exp, "P": exp.head(0)},
                     lg={"H": lg_h, "P": lg_h.head(0)}, guts=guts, people=people)


def _poison(ps: pd.DataFrame) -> pd.DataFrame:
    """Rewrite season TARGET beyond recognition while keeping it VALID data: every player is
    handed a different player's line, and league strikeouts collapse to 2% of PA (which only
    widens the downstream stage denominators, so no stage can go out of range). If any of this
    reached a projection, the clean and poisoned runs could not produce identical numbers."""
    out = ps.copy()
    m = (out.season == TARGET).to_numpy()
    block = out.loc[m].copy()
    ids = block.mlbam_id.to_numpy()
    block.mlbam_id = np.roll(ids, 7)
    block.strikeOuts = (block.plateAppearances * 0.02).astype(int)
    out.loc[m, block.columns] = block.to_numpy()
    return out


def test_train_slice_drops_the_target_season():
    b = _bundle(_player_seasons())
    train = BT.train_slice(b, TARGET)
    assert train.ps["H"].season.max() == TARGET - 1
    assert train.exp["H"].season.max() == TARGET - 1
    assert train.lg["H"].season.max() == TARGET - 1
    assert train.guts.season.max() == TARGET - 1
    assert len(b.ps["H"][b.ps["H"].season == TARGET]) > 0, "fixture must contain a target season"


def test_model_observations_never_reach_the_target_season():
    b = _bundle(_player_seasons())
    train = BT.train_slice(b, TARGET)
    window_end = TARGET - 1
    long = BT._stage_long(train, "H", (window_end - 5, window_end))
    assert long.season.max() == window_end
    assert long.season.min() == window_end - 5


@pytest.mark.parametrize("stage", ["k"])
def test_state_space_projection_ignores_the_target_season(stage):
    clean = _player_seasons()
    ids_a, draws_a, _ = BT.fit_stage_draws(BT.train_slice(_bundle(clean), TARGET), "H", stage,
                                           TARGET, TINY, seed=3)
    ids_b, draws_b, _ = BT.fit_stage_draws(BT.train_slice(_bundle(_poison(clean)), TARGET), "H",
                                           stage, TARGET, TINY, seed=3)
    assert np.array_equal(ids_a, ids_b)
    assert np.allclose(draws_a, draws_b), "season-T data changed the state-space projection"


def test_marcel_and_baselines_ignore_the_target_season():
    clean = _player_seasons()
    b_a, b_b = _bundle(clean), _bundle(_poison(clean))
    ids = BT.eval_population(b_a, "H", TARGET)
    assert len(ids) > 0
    for fn in (BT.marcel_probs, BT.last_season_probs):
        a = fn(BT.train_slice(b_a, TARGET), "H", TARGET)
        c = fn(BT.train_slice(b_b, TARGET), "H", TARGET)
        pd.testing.assert_frame_equal(a.sort_index(), c.sort_index())
    a = BT.league_probs(BT.train_slice(b_a, TARGET), "H", TARGET, ids)
    c = BT.league_probs(BT.train_slice(b_b, TARGET), "H", TARGET, ids)
    pd.testing.assert_frame_equal(a, c)
