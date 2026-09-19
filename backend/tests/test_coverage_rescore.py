"""Unit checks for `keystone.eval.coverage_rescore`.

Reusing the tiny synthetic bundle from `test_backtest_leakage` — same eval population the real
backtest uses, so `build_target_frame` runs on a real-shaped bundle rather than a mock.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from keystone.eval import coverage_rescore as CR
from tests.test_backtest_leakage import TARGET, _bundle, _player_seasons


# ---------------------------------------------------------------- interval math

def test_anchored_interval_shifts_center_and_preserves_width():
    tf = _make_tf(marcel_stat=0.310, q10=0.290, q50=0.300, q90=0.320)
    iv = CR.anchored_intervals(tf, "woba")
    assert np.allclose(iv.q50, 0.310)                             # center = Marcel
    assert np.allclose(iv.q10, 0.310 - 0.010)                     # (q10 - q50) preserved
    assert np.allclose(iv.q90, 0.310 + 0.020)                     # (q90 - q50) preserved


def test_unanchored_interval_matches_sidecar_verbatim():
    tf = _make_tf(marcel_stat=0.999, q10=0.290, q50=0.300, q90=0.320)
    iv = CR.unanchored_intervals(tf, "woba")
    assert np.allclose(iv.q10, 0.290) and np.allclose(iv.q50, 0.300) and np.allclose(iv.q90, 0.320)


def test_cov80_weighted_matches_unweighted_with_equal_weights():
    iv = pd.DataFrame({"q10": [0.0, 0.0, 0.0], "q50": [0.5, 0.5, 0.5], "q90": [1.0, 1.0, 1.0]})
    actual = pd.Series([0.5, 0.5, 1.5])                            # 2 of 3 covered
    out = CR.cov80(iv, actual, weights=np.array([1.0, 1.0, 1.0]))
    assert out["n"] == 3
    assert out["cov80_u"] == 2 / 3
    assert out["cov80_w"] == 2 / 3


def test_cov80_weighting_prefers_the_high_weight_hits():
    iv = pd.DataFrame({"q10": [0.0, 0.0], "q50": [0.5, 0.5], "q90": [1.0, 1.0]})
    actual = pd.Series([0.5, 2.0])                                 # first hits, second misses
    out = CR.cov80(iv, actual, weights=np.array([9.0, 1.0]))
    assert out["cov80_u"] == 0.5
    assert out["cov80_w"] == 0.9                                   # 9/10


def test_anchor_shift_ratio_scales_by_width():
    tf = _make_tf(marcel_stat=0.320, q10=0.290, q50=0.300, q90=0.320)   # shift .020, width .030
    shifts = CR.anchor_shift_ratios([tf])
    s = shifts[(shifts.role == "H") & (shifts.stat == "woba")].s.iloc[0]
    assert np.isclose(s, 0.020 / 0.030)


# ---------------------------------------------------------------- end to end on a real bundle

def _fake_sidecar(target: int, role: str, ids, stat: str,
                  q10: float, q50: float, q90: float) -> pd.DataFrame:
    return pd.DataFrame([{"target": int(target), "role": role, "tier": "tier2",
                          "mlbam_id": int(i), "stat": stat, "pred_mean": q50,
                          "q10": q10, "q50": q50, "q90": q90} for i in ids])


def test_build_target_frame_intersects_eval_and_sidecar_and_marcel():
    b = _bundle(_player_seasons())
    ids = b.ps["H"][b.ps["H"].season == TARGET].mlbam_id.unique()
    sc = _fake_sidecar(TARGET, "H", ids[:20], "woba", 0.290, 0.310, 0.330)
    tf = CR.build_target_frame(b, "H", TARGET, sc)
    assert tf is not None
    # ids come from the intersection of sidecar × eval × Marcel × actual
    assert len(tf.ids) > 0
    assert set(int(i) for i in tf.ids).issubset(set(int(i) for i in ids[:20]))
    assert "woba" in tf.marcel.columns and "woba" in tf.actual.columns


def test_rescore_returns_expected_shape_on_synthetic_bundle():
    b = _bundle(_player_seasons())
    ids = b.ps["H"][b.ps["H"].season == TARGET].mlbam_id.unique()
    # One sidecar row per (player, stat) with a plausible band, so cov80 has something to hit.
    frames = []
    for stat, q10, q50, q90 in [("woba", .290, .320, .360),
                                 ("k_pct", .190, .220, .260),
                                 ("bb_pct", .070, .085, .105),
                                 ("hr_pct", .020, .030, .045),
                                 ("babip", .270, .300, .335)]:
        frames.append(_fake_sidecar(TARGET, "H", ids, stat, q10, q50, q90))
    cov, pct, tfs = CR.rescore(b, pd.concat(frames, ignore_index=True), (TARGET,))
    kinds = set(cov.kind.unique())
    assert kinds == {"anchored", "unanchored"}
    # 5 stats × 2 kinds × 1 target × 1 role (P side has no sidecar rows -> skipped)
    assert len(cov) == 5 * 2
    assert set(cov.stat.unique()) == {"woba", "k_pct", "bb_pct", "hr_pct", "babip"}
    assert set(pct.role.unique()) == {"H"}


def test_acceptance_verdict_reads_the_key_stat_rows():
    dev = pd.DataFrame([
        {"role": "H", "stat": "woba", "kind": "anchored", "cov80_w_mean": 0.80,
         "cov80_u_mean": 0.80, "n_targets": 4, "width_mean": .1, "in_band_w": True,
         "in_band_u": True},
        {"role": "P", "stat": "fip", "kind": "anchored", "cov80_w_mean": 0.60,
         "cov80_u_mean": 0.60, "n_targets": 4, "width_mean": 1, "in_band_w": False,
         "in_band_u": False},
    ])
    holdout = pd.DataFrame([{"role": r, "stat": s, "kind": "anchored", "cov80_w": 0.80,
                             "cov80_u": 0.80, "in_band_w": True, "in_band_u": True, "n": 1,
                             "width": .1}
                            for r in ("H", "P") for s in ("k_pct", "bb_pct", "hr_pct",
                                                         "babip", "woba" if r == "H" else "fip")])
    v = CR.acceptance_verdict(dev, holdout)
    assert v["dev_pass"] is False                # P/fip out of band
    assert v["holdout_pass"] is True             # 10/10 in-band on holdout
    assert v["shipped_claim_stands"] is False    # any leg breaks -> claim doesn't stand


# ---------------------------------------------------------------- helpers

def _make_tf(marcel_stat: float, q10: float, q50: float, q90: float) -> CR.TargetFrame:
    ids = np.array([1, 2, 3], dtype="int64")
    sc = pd.DataFrame([{"mlbam_id": int(i), "stat": "woba",
                        "q10": q10, "q50": q50, "q90": q90} for i in ids])
    marcel = pd.DataFrame({"woba": [marcel_stat] * 3}, index=ids)
    actual = pd.DataFrame({"woba": [q50] * 3}, index=ids)          # unused here
    return CR.TargetFrame(target=2024, role="H", ids=ids,
                          weights=np.array([500.0, 500.0, 500.0]),
                          sidecar=sc, marcel=marcel, actual=actual)
