"""Coverage re-score of the Marcel-anchored shipped intervals.

Pre-registration + verdict live in `docs/coverage_rescore.md`. The estimand and acceptance
rule were written and committed BEFORE this module produced a number; if you are reading this
looking for one, read the pre-registration first.

The shipped h=1 median is Marcel's derived stat (`_anchor_to_marcel` in project.py). The
width around it is Tier 2's. The sidecar carries Tier 2 derived-stat quantiles
(target, role, mlbam_id, stat, q10, q50, q90); the anchoring approximation used here is

    shipped_q10 = marcel_stat + (tier2_q10 - tier2_q50)
    shipped_q50 = marcel_stat
    shipped_q90 = marcel_stat + (tier2_q90 - tier2_q50)

which preserves the two properties `_anchor_to_marcel` enforces (median at Marcel, Tier 2's
width) and ignores the mild non-linearity that reshapes the tail under a per-stage shift.

This module refits nothing and mutates no committed artifact. Actuals and Marcel-derived stats
are computed through the same functions the backtest uses (`stats_from_stage_probs`,
`marcel_probs`), on `train_slice(b, target)` for leakage safety.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from keystone import config as C
from keystone.components import pa_prime
from keystone.eval import backtest as BT

DEV_TARGETS = tuple(C.DEV_TARGETS)
HOLDOUT_TARGET = C.HOLDOUT_TARGET
COV80_BAND = BT.GATE_COV_RANGE               # (.75, .85)
KEY_STAT = BT.KEY_STAT
ROLE_STAGES = BT.ROLE_STAGES


# ---------------------------------------------------------------- per-target frames

@dataclass
class TargetFrame:
    """One target × role: sidecar + Marcel + actual on the same player index."""
    target: int
    role: str
    ids: np.ndarray                       # players in the intersection (sidecar ∩ actual ∩ marcel)
    weights: np.ndarray                   # PA' (H) or IP (P) at the target season
    sidecar: pd.DataFrame                 # index=mlbam_id, columns=(stat, q_p)
    marcel: pd.DataFrame                  # index=mlbam_id, columns=stat -> derived value
    actual: pd.DataFrame                  # same shape as marcel


def build_target_frame(b: BT.Bundle, role: str, target: int,
                       sidecar_all: pd.DataFrame) -> TargetFrame | None:
    """Assemble sidecar + Marcel + actual + weights for one (role, target).

    Returns None if the eval population is empty or if the sidecar has no rows for this cell.
    """
    if b.ps.get(role) is None or b.ps[role].empty:
        return None
    ids_eval = BT.eval_population(b, role, target)
    if len(ids_eval) == 0:
        return None

    sc = sidecar_all[(sidecar_all.target == target) & (sidecar_all.role == role)
                     & (sidecar_all.tier == "tier2")].copy()
    if sc.empty:
        return None
    sc["mlbam_id"] = sc.mlbam_id.astype("int64")

    train = BT.train_slice(b, target)
    env = BT.scoring_env(b, role, target)

    obs_t = b.ps[role]
    obs_t = obs_t[(obs_t.season == target) & obs_t.mlbam_id.isin(ids_eval)]
    pa_t = pd.Series(pa_prime(obs_t, role).to_numpy(dtype=float), index=obs_t.mlbam_id)
    ip_t = (pd.Series(obs_t.outs.to_numpy(dtype=float) / 3.0, index=obs_t.mlbam_id)
            if role == "P" else pd.Series(dtype=float))

    # Actual stat table on the eval population, same code path as the backtest.
    ap = BT.actual_stage_probs(obs_t, role, b.lg[role], target).reindex(ids_eval)
    w = pa_t.reindex(ids_eval).to_numpy()
    ip_v = ip_t.reindex(ids_eval).to_numpy() if role == "P" else None
    actual = pd.DataFrame(
        BT.stats_from_stage_probs({s: ap[s].to_numpy() for s in ROLE_STAGES[role]},
                                  role, env, pa=w, ip=ip_v),
        index=ids_eval)

    # Marcel-derived stats on the same population (same code path).
    mz = BT.marcel_probs(train, role, target).reindex(ids_eval)
    marcel = pd.DataFrame(
        BT.stats_from_stage_probs({s: mz[s].to_numpy(dtype=float) for s in ROLE_STAGES[role]},
                                  role, env, pa=w, ip=ip_v),
        index=ids_eval)

    # Intersect sidecar ids with the eval population (usually equal by construction, but the
    # sidecar was written only for the target's eval intersection at run time, and here we
    # keep only players who also have a Marcel line and an actual — no NaN alignment surprises).
    sc_ids = sorted(set(sc.mlbam_id.unique()))
    keep = np.array(sorted(set(sc_ids) & set(int(i) for i in ids_eval)
                           & set(int(i) for i in marcel.dropna(how="all").index)
                           & set(int(i) for i in actual.dropna(how="all").index)),
                    dtype="int64")
    if not len(keep):
        return None
    sc = sc[sc.mlbam_id.isin(keep)].copy()

    ids_sorted = keep
    weights = (ip_t.reindex(ids_sorted).to_numpy(dtype=float) if role == "P"
               else pa_t.reindex(ids_sorted).to_numpy(dtype=float))

    return TargetFrame(target=target, role=role, ids=ids_sorted, weights=weights,
                       sidecar=sc, marcel=marcel.reindex(ids_sorted),
                       actual=actual.reindex(ids_sorted))


# ---------------------------------------------------------------- intervals + coverage

STATS_BY_ROLE = {"H": ["k_pct", "bb_pct", "hr_pct", "babip", "woba"],
                 "P": ["k_pct", "bb_pct", "hr_pct", "babip", "fip"]}


def anchored_intervals(tf: TargetFrame, stat: str) -> pd.DataFrame:
    """Return (mlbam_id, q10, q50, q90) for the SHIPPED-APPROXIMATION interval:
    marcel + (tier2_q_p - tier2_q50) for each quantile."""
    sc = tf.sidecar[tf.sidecar.stat == stat].set_index("mlbam_id").reindex(tf.ids)
    m = tf.marcel[stat].reindex(tf.ids)
    delta_lo = (sc.q10 - sc.q50).to_numpy(dtype=float)
    delta_hi = (sc.q90 - sc.q50).to_numpy(dtype=float)
    center = m.to_numpy(dtype=float)
    return pd.DataFrame({"mlbam_id": tf.ids,
                         "q10": center + delta_lo,
                         "q50": center,
                         "q90": center + delta_hi})


def unanchored_intervals(tf: TargetFrame, stat: str) -> pd.DataFrame:
    """The sidecar's Tier 2 intervals, aligned to the same player index."""
    sc = tf.sidecar[tf.sidecar.stat == stat].set_index("mlbam_id").reindex(tf.ids)
    return pd.DataFrame({"mlbam_id": tf.ids,
                         "q10": sc.q10.to_numpy(dtype=float),
                         "q50": sc.q50.to_numpy(dtype=float),
                         "q90": sc.q90.to_numpy(dtype=float)})


def cov80(intervals: pd.DataFrame, actual: pd.Series, weights: np.ndarray | None) -> dict:
    """PA/IP-weighted and unweighted 80% empirical coverage, plus n and mean interval width."""
    a = actual.to_numpy(dtype=float)
    q10 = intervals.q10.to_numpy(dtype=float)
    q90 = intervals.q90.to_numpy(dtype=float)
    hit = (q10 <= a) & (a <= q90)
    ok = np.isfinite(a) & np.isfinite(q10) & np.isfinite(q90)
    if weights is not None:
        w = np.asarray(weights, dtype=float)
        ok = ok & np.isfinite(w) & (w > 0)
        if not ok.any():
            return {"n": 0, "cov80_w": None, "cov80_u": None, "width": None}
        ww = w[ok] / w[ok].sum()
        cov_w = float(np.sum(ww * hit[ok]))
    else:
        cov_w = None
    if not ok.any():
        return {"n": 0, "cov80_w": cov_w, "cov80_u": None, "width": None}
    cov_u = float(np.mean(hit[ok]))
    width = float(np.mean((q90 - q10)[ok]))
    return {"n": int(ok.sum()), "cov80_w": cov_w, "cov80_u": cov_u, "width": width}


# ---------------------------------------------------------------- anchor-shift distribution

def anchor_shift_ratios(frames: list[TargetFrame]) -> pd.DataFrame:
    """For each (role, stat, target, player):
        s = (marcel - tier2_q50) / (tier2_q90 - tier2_q10)
    Positive s ⇒ anchor moved the median up. Percentiles reported by (role, stat).
    Only stats present in both the sidecar and the Marcel table are scored."""
    rows = []
    for tf in frames:
        sc_stats = set(tf.sidecar.stat.unique())
        for stat in STATS_BY_ROLE[tf.role]:
            if stat not in sc_stats or stat not in tf.marcel.columns:
                continue
            sc = tf.sidecar[tf.sidecar.stat == stat].set_index("mlbam_id").reindex(tf.ids)
            width = (sc.q90 - sc.q10).to_numpy(dtype=float)
            shift = tf.marcel[stat].to_numpy(dtype=float) - sc.q50.to_numpy(dtype=float)
            ok = np.isfinite(shift) & np.isfinite(width) & (width > 0)
            s = shift[ok] / width[ok]
            for v in s:
                rows.append({"role": tf.role, "stat": stat, "target": tf.target, "s": float(v)})
    return pd.DataFrame(rows)


def shift_percentiles(shifts: pd.DataFrame,
                      qs: tuple = (0.10, 0.25, 0.50, 0.75, 0.90, 0.99)) -> pd.DataFrame:
    """Per (role, stat) percentiles of |shift| / width and of the signed shift."""
    out = []
    for (role, stat), grp in shifts.groupby(["role", "stat"]):
        row = {"role": role, "stat": stat, "n": int(len(grp))}
        signed = grp.s.to_numpy()
        absv = np.abs(signed)
        for q in qs:
            row[f"|s|_p{int(q * 100)}"] = float(np.quantile(absv, q))
        row["signed_median"] = float(np.median(signed))
        row["signed_mean"] = float(np.mean(signed))
        out.append(row)
    return pd.DataFrame(out).sort_values(["role", "stat"]).reset_index(drop=True)


# ---------------------------------------------------------------- entry

def rescore(bundle: BT.Bundle, sidecar: pd.DataFrame, targets: tuple[int, ...]
            ) -> tuple[pd.DataFrame, pd.DataFrame, list[TargetFrame]]:
    """Build frames + score coverage for `targets`. Returns (cov_table, shift_pct_table, frames).

    cov_table: one row per (target, role, stat, kind) where kind ∈ {anchored, unanchored}.
    shift_pct_table: percentiles of s = (marcel − tier2_q50) / (tier2_q90 − tier2_q10)."""
    frames: list[TargetFrame] = []
    for target in targets:
        for role in ("H", "P"):
            tf = build_target_frame(bundle, role, int(target), sidecar)
            if tf is not None:
                frames.append(tf)

    cov_rows = []
    for tf in frames:
        sc_stats = set(tf.sidecar.stat.unique())
        for stat in STATS_BY_ROLE[tf.role]:
            if stat not in sc_stats or stat not in tf.actual.columns:
                continue
            for kind, get in (("anchored", anchored_intervals),
                              ("unanchored", unanchored_intervals)):
                iv = get(tf, stat)
                stats = cov80(iv, tf.actual[stat], tf.weights)
                cov_rows.append({"target": tf.target, "role": tf.role, "stat": stat,
                                 "kind": kind, **stats})
    cov = pd.DataFrame(cov_rows)
    shifts = anchor_shift_ratios(frames)
    pct = shift_percentiles(shifts)
    return cov, pct, frames


# ---------------------------------------------------------------- pretty printing

def summarise_dev(cov: pd.DataFrame, dev_targets: tuple[int, ...]) -> pd.DataFrame:
    """PA-weighted mean cov80 across dev targets, per (role, stat, kind), plus in-band flag."""
    dev = cov[cov.target.isin(dev_targets)].copy()
    grp = (dev.groupby(["role", "stat", "kind"])
              .apply(lambda d: pd.Series({
                  "cov80_w_mean": d.cov80_w.mean() if d.cov80_w.notna().any() else np.nan,
                  "cov80_u_mean": d.cov80_u.mean() if d.cov80_u.notna().any() else np.nan,
                  "n_targets": int(len(d)),
                  "width_mean": d.width.mean()}), include_groups=False)
              .reset_index())
    grp["in_band_w"] = grp.cov80_w_mean.between(*COV80_BAND)
    grp["in_band_u"] = grp.cov80_u_mean.between(*COV80_BAND)
    return grp


def summarise_one_target(cov: pd.DataFrame, target: int) -> pd.DataFrame:
    """Per (role, stat, kind) on a single target with in-band flags."""
    sub = cov[cov.target == target].copy()
    sub["in_band_w"] = sub.cov80_w.between(*COV80_BAND)
    sub["in_band_u"] = sub.cov80_u.between(*COV80_BAND)
    return sub


def acceptance_verdict(dev_summary: pd.DataFrame, holdout_summary: pd.DataFrame) -> dict:
    """Pre-registered rule: key-stat dev PA-weighted mean in band for BOTH roles AND ≥ 8/10
    (role, stat) rows in-band on the holdout (anchored, PA-weighted)."""
    key_rows = dev_summary[dev_summary.kind == "anchored"].copy()
    key_h = key_rows[(key_rows.role == "H") & (key_rows.stat == KEY_STAT["H"])].iloc[0]
    key_p = key_rows[(key_rows.role == "P") & (key_rows.stat == KEY_STAT["P"])].iloc[0]
    dev_pass = bool(key_h.in_band_w and key_p.in_band_w)

    hold_anchored = holdout_summary[holdout_summary.kind == "anchored"]
    hold_in = int(hold_anchored.in_band_w.sum())
    hold_total = int(len(hold_anchored))
    hold_pass = hold_in >= 8

    return {"dev_key_H": float(key_h.cov80_w_mean),
            "dev_key_P": float(key_p.cov80_w_mean),
            "dev_pass": dev_pass,
            "holdout_in_band": hold_in,
            "holdout_of": hold_total,
            "holdout_pass": hold_pass,
            "shipped_claim_stands": dev_pass and hold_pass}


def load_sidecar(artifacts_dir: Path | None = None) -> pd.DataFrame:
    p = Path(artifacts_dir or C.ARTIFACTS) / "backtest_predictions.parquet"
    if not p.exists():
        raise FileNotFoundError(f"missing sidecar {p}; run `make backtest` first")
    return pd.read_parquet(p)


# ---------------------------------------------------------------- 2026-09-18: fix re-score
# The `project.py` fix (2026-09-18) makes the shipped h=1 interval quantiles the
# posterior-*predictive* object `interval_coverage` was always measuring for cov80:
# anchored stage draws pushed through `simulate_season` at Marcel PT. Pre-registration
# and prediction: `docs/coverage_rescore.md` 2026-09-18 section. This block scores the
# new object on dev 2021-2024 without refitting (a refit at 4 dev targets ≈ 140 min).
#
# Approximation, stated up front. The sidecar stores derived-stat quantiles (not
# stage-level draws), so the exact anchored predictive cannot be reconstructed without
# a refit. Instead:
#   1. Talent posterior-on-rate sd per player-stat is approximated from the sidecar's
#      80% width under a Gaussian assumption: sd_talent ≈ (q90 − q10) / 2.5631.
#   2. Binomial variance at Marcel PT is measured directly by running the writer's own
#      `_predictive_stats_h1` on a degenerate stage distribution (Marcel stage rates
#      broadcast to n_sim draws — the anchor pushed to a point, no talent spread).
#   3. Predictive sd = sqrt(sd_talent² + sd_binom²), assuming independence. This is
#      exact when the two are independent (they are, by construction of the writer:
#      binomial draws are conditional on the anchored talent draws).
#   4. Interval: center = Marcel derived stat, q10/q90 = center ± 1.2816·sd (normal
#      tails). Skew from the derived-stat function is ignored — for wOBA (linear in
#      stage counts) this is fine; for FIP (division by IP) the tail is slightly
#      right-skewed and cov80 may under-report by ≤ .02.
#
# Approximation direction of error: (3) is exact under independence; (1) treats the
# tier2 posterior as Gaussian, which is a mild under-statement of the tail width when
# the posterior is skewed (small effect on the cov80 given the binomial layer dominates
# on most rows). Overall, the approximation should be within ±.02 of a full-refit
# answer on cov80.


def _predictive_binomial_sd(role: str, target: int, bundle: BT.Bundle,
                            ids: np.ndarray, marcel_pt: pd.Series, seed: int,
                            n_sim: int = 2000) -> pd.DataFrame:
    """Binomial-only sd of each derived stat at Marcel stage rates + Marcel PT.

    Runs the writer's own `_predictive_stats_h1` (from `keystone.project`) on
    Marcel stage rates broadcast to (n_players, n_sim) — a stage distribution with
    no talent spread — so the returned sd is exactly the binomial-noise contribution
    at Marcel PT that `simulate_season` produces in `projections.parquet`.

    Returns a DataFrame indexed by mlbam_id with one column per derived stat.
    """
    from keystone.project import STATS as PROJ_STATS
    from keystone.project import _predictive_stats_h1

    train = BT.train_slice(bundle, target)
    env = BT.scoring_env(bundle, role, target)
    m_rates = BT.marcel_probs(train, role, target).reindex(ids)
    stages = BT.ROLE_STAGES[role]

    stage_draws = {}
    for s in stages:
        r = m_rates[s].to_numpy(dtype=float)
        stage_draws[s] = np.broadcast_to(r[:, None], (len(ids), n_sim)).copy()

    pt = marcel_pt.reindex(ids).to_numpy(dtype=float)
    stats_pred = _predictive_stats_h1(stage_draws, role, env, pt, seed=seed)
    sd = {s: np.nanstd(stats_pred[s], axis=-1) for s in PROJ_STATS[role]}
    return pd.DataFrame(sd, index=pd.Index(ids, name="mlbam_id"))


def anchored_predictive_intervals(tf: TargetFrame, stat: str,
                                   binom_sd: pd.DataFrame) -> pd.DataFrame:
    """Return q10/q50/q90 of the NEW shipped interval object at Marcel PT.

    center = marcel derived stat; predictive sd = sqrt(tier2 sd² + binomial sd²).
    See the module-level 2026-09-18 comment for the approximation details.
    """
    sc = tf.sidecar[tf.sidecar.stat == stat].set_index("mlbam_id").reindex(tf.ids)
    sd_talent = (sc.q90 - sc.q10).to_numpy(dtype=float) / 2.5631
    sd_binom = binom_sd[stat].reindex(tf.ids).to_numpy(dtype=float)
    predictive_sd = np.sqrt(np.where(np.isfinite(sd_talent), sd_talent ** 2, 0.0)
                            + np.where(np.isfinite(sd_binom), sd_binom ** 2, 0.0))
    center = tf.marcel[stat].reindex(tf.ids).to_numpy(dtype=float)
    return pd.DataFrame({"mlbam_id": tf.ids,
                         "q10": center - 1.2815515655446004 * predictive_sd,
                         "q50": center,
                         "q90": center + 1.2815515655446004 * predictive_sd})


def rescore_predictive(bundle: BT.Bundle, sidecar: pd.DataFrame,
                       targets: tuple[int, ...], seed: int = 7,
                       n_sim: int = 2000) -> pd.DataFrame:
    """cov80 of the NEW shipped intervals (anchored predictive at Marcel PT), per
    (target, role, stat), on the same eval intersection the old re-score uses.

    One row per (target, role, stat) with n, cov80_w, cov80_u, width. See the
    module-level 2026-09-18 comment for the approximation.
    """
    from keystone.models import marcel as MARCEL

    rows = []
    for target in targets:
        for role in ("H", "P"):
            tf = build_target_frame(bundle, role, int(target), sidecar)
            if tf is None:
                continue
            m_pt = MARCEL.marcel_playing_time(BT.train_slice(bundle, int(target)).ps[role],
                                              role, int(target))
            binom_sd = _predictive_binomial_sd(role, int(target), bundle, tf.ids,
                                               m_pt, seed=seed, n_sim=n_sim)
            sc_stats = set(tf.sidecar.stat.unique())
            for stat in STATS_BY_ROLE[role]:
                if stat not in sc_stats or stat not in tf.actual.columns:
                    continue
                iv = anchored_predictive_intervals(tf, stat, binom_sd)
                stats = cov80(iv, tf.actual[stat], tf.weights)
                rows.append({"target": tf.target, "role": role, "stat": stat,
                             "kind": "anchored_predictive",
                             "n_sim": int(n_sim), **stats})
    return pd.DataFrame(rows)


def summarise_dev_predictive(cov: pd.DataFrame,
                              dev_targets: tuple[int, ...]) -> pd.DataFrame:
    """PA-weighted mean cov80 across dev targets on the anchored-predictive rows."""
    dev = cov[cov.target.isin(dev_targets)].copy()
    grp = (dev.groupby(["role", "stat"])
              .apply(lambda d: pd.Series({
                  "cov80_w_mean": d.cov80_w.mean() if d.cov80_w.notna().any() else np.nan,
                  "cov80_u_mean": d.cov80_u.mean() if d.cov80_u.notna().any() else np.nan,
                  "n_targets": int(len(d)),
                  "width_mean": d.width.mean()}), include_groups=False)
              .reset_index())
    grp["in_band_w"] = grp.cov80_w_mean.between(*COV80_BAND)
    return grp
