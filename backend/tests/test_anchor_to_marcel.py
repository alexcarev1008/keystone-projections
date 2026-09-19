"""_anchor_to_marcel is the one transform sitting between the validated Tier 2 posterior
and every shipped h=1 median. When Tier 2 fails the §6 gate (as it currently does), production
shifts each stage's draws in logit space so the h=1 median lands on Marcel's rate, keeping the
posterior spread and aging trajectory intact.

Everything on a shipped player page — the summary cards' q50, the fan-chart median, the
component panel medians, the leaderboard sort key — flows through this. It had no test before.
"""
from __future__ import annotations

import numpy as np

from keystone.project import _anchor_to_marcel


def _logit(x):
    x = np.clip(x, 1e-9, 1 - 1e-9)
    return np.log(x / (1 - x))


def test_h1_median_lands_on_marcel_rate():
    rng = np.random.default_rng(0)
    # (n_players, n_horizons, n_draws) of talent probabilities on a K% scale
    P = 1 / (1 + np.exp(-(rng.normal(-1.2, 0.25, size=(50, 4, 500)))))
    marcel = np.clip(rng.normal(0.22, 0.03, size=50), 0.02, 0.5)
    out = _anchor_to_marcel(P, marcel)
    med = np.median(out[:, 0, :], axis=-1)
    # Exact in logit space; back on the rate scale q50 lands on Marcel to numerical precision.
    assert np.allclose(med, marcel, atol=1e-6), f"h=1 median off Marcel by {(med - marcel).max()}"


def test_anchor_preserves_logit_spread():
    """The whole point of the anchor is: bands and aging come from Tier 2, only the level moves.
    So logit-scale spread must be invariant to the shift (up to the clip)."""
    rng = np.random.default_rng(1)
    P = 1 / (1 + np.exp(-(rng.normal(-1.5, 0.4, size=(30, 4, 300)))))
    marcel = np.full(30, 0.10)                   # aggressive shift to catch clipping surprises
    out = _anchor_to_marcel(P, marcel)
    lp_in = _logit(P.astype(np.float64))
    lp_out = _logit(out.astype(np.float64))
    for h in range(4):
        # Spread within each player-horizon is preserved (each draw shifted by a constant).
        s_in = lp_in[:, h, :].std(axis=-1)
        s_out = lp_out[:, h, :].std(axis=-1)
        assert np.allclose(s_in, s_out, atol=1e-4), (
            f"h={h} logit-sd changed: max |Δ| = {np.abs(s_in - s_out).max():.4g}")


def test_shift_is_the_same_at_every_horizon():
    """The shift is decided at h=1 and applied to every horizon, so aging drift (h=2..4)
    comes from Tier 2 unchanged after the h=1 anchor."""
    rng = np.random.default_rng(2)
    P = 1 / (1 + np.exp(-(rng.normal(0.0, 0.3, size=(20, 4, 400)))))
    marcel = np.clip(rng.uniform(0.15, 0.55, size=20), 0.02, 0.85)
    out = _anchor_to_marcel(P, marcel)
    delta = _logit(out.astype(np.float64)) - _logit(P.astype(np.float64))
    # For each player, the additive shift is the same across every (horizon, draw).
    for i in range(20):
        d = delta[i].ravel()
        assert np.allclose(d, d[0], atol=1e-5), (
            f"player {i} anchor shift varies across (h, draw): max |Δ| = {(d - d[0]).max()}")


def test_marcel_equal_to_tier2_median_is_a_no_op():
    """If Marcel already agrees with Tier 2's h=1 median, the shift is 0 and P is returned
    (up to the clip round-trip)."""
    rng = np.random.default_rng(3)
    P = 1 / (1 + np.exp(-(rng.normal(-2.0, 0.35, size=(10, 4, 200)))))
    marcel_matched = np.median(P[:, 0, :], axis=-1)
    out = _anchor_to_marcel(P, marcel_matched)
    assert np.allclose(out, P, atol=1e-6)


def test_marcel_nan_propagates_and_does_not_touch_other_players():
    """A player with no Marcel line (NaN rate) currently yields NaN across every horizon and
    draw. That's the case project.projections_frame filters as 'orphan' before shipping
    (STATUS artifact check B); the anchor itself should not silently invent a value."""
    P = np.full((3, 4, 100), 0.30, dtype=np.float32)
    marcel = np.array([0.25, np.nan, 0.35])
    out = _anchor_to_marcel(P, marcel)
    assert np.allclose(np.median(out[0, 0, :]), 0.25, atol=1e-6)
    assert np.allclose(np.median(out[2, 0, :]), 0.35, atol=1e-6)
    assert np.all(np.isnan(out[1]))
