"""Predictive-interval writer (`project._predictive_stats_h1`) is what makes
`projections.parquet` interval quantiles match the object `eval/backtest.py.interval_coverage`
scores for cov80. Pre-registration + rationale: `docs/coverage_rescore.md`
(2026-09-18 section).

Two properties this test pins down:

1. **Adds binomial noise.** For a finite PA the predictive interval must be strictly wider
   than the posterior-on-rate interval on the same stage draws (`_quantile_frame` of the
   derived-stat draws directly). If it weren't, the whole point of the fix would be moot.

2. **Converges as PA → ∞.** The binomial contribution to per-stage variance is
   `p*(1-p)/n`, which vanishes in n. So the predictive interval must shrink toward the
   posterior-on-rate one — not necessarily equal, but the ratio of widths must approach 1.
"""
from __future__ import annotations

import numpy as np

from keystone.components import derive_hitter
from keystone.project import HITTER_STAGES, _predictive_stats_h1, _quantile_frame


ENV_H = {"wBB": 0.696, "wHBP": 0.726, "w1B": 0.883, "w2B": 1.249, "w3B": 1.577,
         "wHR": 2.048, "sf_rate": 0.008}


def _stage_draws(n_players: int, n_draws: int, seed: int = 0) -> dict:
    """Realistic-ish per-stage talent draws for hitters, seeded so widths are stable."""
    rng = np.random.default_rng(seed)
    # centered on league-ish per-stage rates; small talent spread so tail counts do
    # not blow up.
    means = {"k": -1.25, "bb": -2.6, "hbp": -3.8, "hr": -3.2, "hit_bip": -0.9,
             "xbh": -1.4, "triple": -3.0}
    sds = {"k": 0.25, "bb": 0.25, "hbp": 0.2, "hr": 0.4, "hit_bip": 0.15,
           "xbh": 0.25, "triple": 0.3}
    out = {}
    for s in HITTER_STAGES:
        mu = means[s] + rng.normal(0.0, 0.05, size=(n_players, 1))
        z = rng.normal(0.0, 1.0, size=(n_players, n_draws))
        out[s] = 1.0 / (1.0 + np.exp(-(mu + sds[s] * z)))
    return out


def _rate_stats_h(P: dict, env: dict) -> dict:
    return derive_hitter(P, env, env["sf_rate"])


def test_predictive_wider_than_posterior_on_rate_at_finite_pa():
    """500 PA is a full season; the binomial layer should still add meaningful width to
    every H stat that has any non-zero rate."""
    n_players, n_draws = 12, 800
    P = _stage_draws(n_players, n_draws, seed=1)
    m_pt = np.full(n_players, 500.0)
    stats_pred = _predictive_stats_h1(P, "H", ENV_H, m_pt, seed=1)
    stats_rate = _rate_stats_h(P, ENV_H)

    for stat in ("k_pct", "bb_pct", "hr_pct", "babip", "woba"):
        q_pred = _quantile_frame(np.asarray(stats_pred[stat]))
        q_rate = _quantile_frame(np.asarray(stats_rate[stat]))
        w_pred = q_pred["q90"] - q_pred["q10"]
        w_rate = q_rate["q90"] - q_rate["q10"]
        # Predictive must be at least as wide on every player, strictly wider on the
        # weighted average (no ties by chance with n=12 players).
        assert np.all(w_pred >= w_rate - 1e-9), (
            f"{stat}: predictive band narrower than posterior-on-rate for some player")
        assert np.mean(w_pred) > np.mean(w_rate) * 1.02, (
            f"{stat}: predictive band not meaningfully wider than posterior-on-rate "
            f"(mean pred {np.mean(w_pred):.5f} vs rate {np.mean(w_rate):.5f})")


def test_predictive_converges_to_posterior_on_rate_as_pa_grows():
    """Binomial-noise contribution to per-stage sd is p*(1-p)/sqrt(n); the predictive band
    must approach the posterior-on-rate band from above as n_pa grows."""
    n_players, n_draws = 8, 800
    P = _stage_draws(n_players, n_draws, seed=2)
    stats_rate = _rate_stats_h(P, ENV_H)
    q_rate = _quantile_frame(np.asarray(stats_rate["woba"]))
    w_rate = q_rate["q90"] - q_rate["q10"]

    ratios = []
    for n_pa in (400, 4_000, 40_000):
        m_pt = np.full(n_players, float(n_pa))
        stats_pred = _predictive_stats_h1(P, "H", ENV_H, m_pt, seed=2)
        q_pred = _quantile_frame(np.asarray(stats_pred["woba"]))
        w_pred = q_pred["q90"] - q_pred["q10"]
        ratios.append(float(np.mean(w_pred / w_rate)))

    # Monotone approach to 1 from above.
    assert ratios[0] > ratios[1] > ratios[2], (
        f"widths did not shrink monotonically with PA: {ratios}")
    assert ratios[2] < 1.1, (
        f"predictive band did not converge to rate band at 40k PA (ratio {ratios[2]:.3f})")
    assert ratios[0] > 1.2, (
        f"binomial contribution is negligible even at 400 PA (ratio {ratios[0]:.3f}); "
        "the test can't distinguish the two objects")
