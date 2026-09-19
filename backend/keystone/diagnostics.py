"""Phase 6.5 — Fable context pack (FABLE_MISSIONS.md §3).

Consumes only what is already on disk: `data/artifacts/` (backtest.json, meta.json, aging.parquet)
and `data/processed/*`. No model fits, no long computations, so `make diagnostics` finishes in
seconds. Every file listed in FABLE_MISSIONS.md §3 is emitted; when the source data for a column
is not stored anywhere (e.g. per-player Tier 2 posterior draws), the column is left null and the
gap is called out in CONTEXT.md so Fable can spec a sidecar via HANDOFF.md.

Outputs to `docs/fable_context/`:
  CONTEXT.md               <=400 lines, the project in one page
  code_map.md              one line per backend file
  backtest_summary.csv     backtest.json rows
  residuals_by_bucket.csv  per-player buckets — Marcel always; Tier 2/3 when the sidecar exists
  pit_histograms.csv       Marcel pooled normal-approx PIT; Tier 2/3 real PIT from the sidecar
  posterior_summaries.csv  meta.json (target=window_end) + backtest diag rows, enriched from the
                           posteriors sidecar when present
  aging_curves.csv         from aging.parquet (mean only; q10/q90 need per-draw store)
  park_effects.csv         meta.json top/bottom_hr_parks; other stages null
  biggest_misses.csv       40 largest |error| per Marcel × dev target × role (+Tier 2/3 rows when
                           the sidecar exists)
  stage_correlations.csv   per-player stage residuals in the last window
  pt_summary.csv           Marcel PT vs actual PA/IP by age + prior-PT bucket
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from keystone import config as C
from keystone import league as LG
from keystone.components import (HITTER_STAGES, PARK_STAGES, PITCHER_STAGES,
                                 derive_hitter, derive_pitcher, pa_prime,
                                 stage_counts)
from keystone.data import mlb_api
from keystone.eval.backtest import (KEY_STAT, ROLE_STAGES, STATS, DIAG_STAT,
                                    Bundle, actual_stage_probs, eval_population,
                                    load_bundle, scoring_env, stats_from_stage_probs)
from keystone.models import marcel as MARCEL

ROLES = ("H", "P")
AGE_BUCKETS = ((None, 24, "<=24"), (25, 27, "25-27"), (28, 30, "28-30"),
               (31, 33, "31-33"), (34, None, ">=34"))
PT_BUCKETS_H = ((0, 149, "<150"), (150, 400, "150-400"), (401, 10_000, ">400"))
PT_BUCKETS_P = PT_BUCKETS_H          # BF' uses the same edges (they were chosen for both)
HISTORY_BUCKETS = ((1, 1, "1"), (2, 2, "2"), (3, 3, "3+"))
CAP_ROWS = 2000
# Per-file caps. residuals_by_bucket legitimately grows with the number of tiers scored
# (3 tiers x role x stat x target x bucket ~ 4.1k rows); truncating it would silently drop
# whole tiers, so it gets its own larger cap.
CAP_OVERRIDES = {"residuals_by_bucket.csv": 6000}
MAX_CONTEXT_LINES = 400


# ---------------------------------------------------------------- IO

def _load_json(p: Path) -> dict:
    return json.loads(p.read_text()) if p.exists() else {}


def _write_csv(df: pd.DataFrame, path: Path, cap: int = CAP_ROWS) -> int:
    if len(df) > cap:
        df = df.head(cap)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return len(df)


def _load_parquet(p: Path) -> pd.DataFrame | None:
    return pd.read_parquet(p) if p.exists() else None


# ---------------------------------------------------------------- 1. backtest_summary

def build_backtest_summary(bt: dict) -> pd.DataFrame:
    rows = [r for r in bt.get("rows", []) if r.get("stat") != DIAG_STAT]
    if not rows:
        return pd.DataFrame(columns=["target", "role", "tier", "stat", "n",
                                     "rmse", "mae", "cov50", "cov80"])
    df = pd.DataFrame(rows)[["target", "role", "tier", "stat", "n",
                             "rmse", "mae", "cov50", "cov80"]]
    return df.sort_values(["role", "tier", "stat", "target"]).reset_index(drop=True)


# ---------------------------------------------------------------- 2. posterior_summaries

def build_posterior_summaries(bt: dict, meta: dict,
                              sidecar: pd.DataFrame | None = None) -> pd.DataFrame:
    """meta.json stages (target=window_end) + backtest diagnostic rows (target-level r_hat/div).

    When the posteriors sidecar exists, per-target rows carry tau/sigma_pop/lam/sigma_age/park_sd
    means and sds plus ess_bulk_min. The DIAG_STAT rows in backtest.json embed the same numbers
    (as of M1) and are only used as a fallback when the sidecar is missing.
    """
    window_end = meta.get("window_end")
    rows: list[dict] = []
    for key, s in (meta.get("stages") or {}).items():
        role, stage = key.split("/", 1)
        rows.append({"role": role, "stage": stage, "target": window_end,
                     "tier": meta.get("production_tier", {}).get(role, "tier2"),
                     "tau_mean": s.get("tau_mean"),
                     "sigma_pop_mean": s.get("sigma_pop_mean"),
                     "park_sd_mean": s.get("park_sd_mean"),
                     "lam_mean": None, "sigma_age_mean": None,
                     "tau_sd": None, "sigma_pop_sd": None,
                     "lam_sd": None, "sigma_age_sd": None, "park_sd_sd": None,
                     "ess_bulk_min": None,
                     "max_rhat": s.get("max_rhat"),
                     "divergences": s.get("divergences")})
    if sidecar is not None and not sidecar.empty:
        for r in sidecar.itertuples(index=False):
            rows.append({"role": r.role, "stage": r.stage, "target": int(r.target),
                         "tier": r.tier,
                         "tau_mean": r.tau_mean, "tau_sd": r.tau_sd,
                         "sigma_pop_mean": r.sigma_pop_mean,
                         "sigma_pop_sd": r.sigma_pop_sd,
                         "lam_mean": r.lam_mean, "lam_sd": r.lam_sd,
                         "sigma_age_mean": r.sigma_age_mean,
                         "sigma_age_sd": r.sigma_age_sd,
                         "park_sd_mean": r.park_sd_mean,
                         "park_sd_sd": r.park_sd_sd,
                         "ess_bulk_min": r.ess_bulk_min,
                         "max_rhat": r.max_rhat,
                         "divergences": r.divergences})
    else:
        for row in bt.get("rows", []):
            if row.get("stat") != DIAG_STAT or not row.get("diagnostics"):
                continue
            for stage, d in row["diagnostics"].items():
                rows.append({"role": row["role"], "stage": stage, "target": row["target"],
                             "tier": row["tier"],
                             "tau_mean": d.get("tau_mean"),
                             "tau_sd": d.get("tau_sd"),
                             "sigma_pop_mean": d.get("sigma_pop_mean"),
                             "sigma_pop_sd": d.get("sigma_pop_sd"),
                             "lam_mean": d.get("lam_mean"),
                             "lam_sd": d.get("lam_sd"),
                             "sigma_age_mean": d.get("sigma_age_mean"),
                             "sigma_age_sd": d.get("sigma_age_sd"),
                             "park_sd_mean": d.get("park_sd_mean"),
                             "park_sd_sd": d.get("park_sd_sd"),
                             "ess_bulk_min": d.get("ess_bulk_min"),
                             "max_rhat": d.get("max_rhat"),
                             "divergences": d.get("divergences")})
    return pd.DataFrame(rows).sort_values(["role", "stage", "target", "tier"]).reset_index(drop=True)


# ---------------------------------------------------------------- 3. aging_curves

def build_aging_curves(artifacts_dir: Path) -> pd.DataFrame:
    p = artifacts_dir / "aging.parquet"
    if not p.exists():
        return pd.DataFrame(columns=["role", "stage", "age", "mean", "q10", "q90"])
    df = pd.read_parquet(p).rename(columns={"stat": "stage", "value": "mean"})
    df["q10"] = np.nan
    df["q90"] = np.nan
    return df[["role", "stage", "age", "mean", "q10", "q90"]].reset_index(drop=True)


# ---------------------------------------------------------------- 4. park_effects

def build_park_effects(meta: dict) -> pd.DataFrame:
    rows: list[dict] = []
    stages_meta = meta.get("stages") or {}
    for key, s in stages_meta.items():
        role, stage = key.split("/", 1)
        for group in ("top_hr_parks", "bottom_hr_parks"):
            for v in s.get(group, []) or []:
                rows.append({"role": role, "stage": stage,
                             "venue_id": v.get("venue_id"),
                             "venue_name": v.get("venue_name"),
                             "phi_mean": v.get("phi"),
                             "phi_sd": None,
                             "park_sd_mean": s.get("park_sd_mean")})
    # Also emit one summary row per (role, park stage) so Fable sees which stages exist.
    seen = {(r["role"], r["stage"]) for r in rows}
    for key, s in stages_meta.items():
        role, stage = key.split("/", 1)
        if stage not in PARK_STAGES or (role, stage) in seen:
            continue
        rows.append({"role": role, "stage": stage,
                     "venue_id": None, "venue_name": None,
                     "phi_mean": None, "phi_sd": None,
                     "park_sd_mean": s.get("park_sd_mean")})
    return pd.DataFrame(rows).sort_values(["role", "stage", "phi_mean"],
                                          na_position="last").reset_index(drop=True)


# ---------------------------------------------------------------- 5. Marcel per-target predictions

@dataclass
class MarcelRun:
    pred: pd.DataFrame     # index=mlbam_id; columns = STATS[role]
    actual: pd.DataFrame   # same shape
    ids: np.ndarray
    pa: pd.Series          # PA' or BF' in target T
    age: pd.Series         # age in T
    prior_pa: pd.Series    # PA' in T-1
    history_years: pd.Series  # count of T-3..T-1 seasons with PA' >= 1


def _marcel_target(b: Bundle, role: str, target: int) -> MarcelRun | None:
    ids = eval_population(b, role, target)
    if len(ids) == 0:
        return None
    ps = b.ps[role]
    obs_t = ps[(ps.season == target) & ps.mlbam_id.isin(ids)]
    if obs_t.empty:
        return None
    pa = pd.Series(pa_prime(obs_t, role).to_numpy(dtype=float), index=obs_t.mlbam_id)
    ip = (pd.Series(obs_t.outs.to_numpy(dtype=float) / 3.0, index=obs_t.mlbam_id)
          if role == "P" else None)
    env = scoring_env(b, role, target)

    # Actual observed derived stats — same formula every tier uses.
    ap = actual_stage_probs(obs_t, role, b.lg[role], target).reindex(ids)
    w = pa.reindex(ids).to_numpy()
    ip_v = ip.reindex(ids).to_numpy() if role == "P" else None
    actual = pd.DataFrame(
        stats_from_stage_probs({s: ap[s].to_numpy() for s in ROLE_STAGES[role]},
                               role, env, pa=w, ip=ip_v), index=ids)

    # Marcel stage rates on pre-T data.
    train_ps = ps[ps.season < target]
    ages = mlb_api.season_age(b.people.set_index("mlbam_id")["birth_date"], target)
    ev = MARCEL.events_table(train_ps, role)
    mz = MARCEL.marcel(ev, role, target, ages).set_index("mlbam_id")[ROLE_STAGES[role]]
    mz = mz.reindex(ids)
    pred = pd.DataFrame(
        stats_from_stage_probs({s: mz[s].to_numpy(dtype=float) for s in ROLE_STAGES[role]},
                               role, env, pa=w, ip=ip_v), index=ids)

    age_series = pd.Series(ages).reindex(ids).astype(float)
    prev = ps[ps.season == target - 1]
    prior_pa_series = pd.Series(pa_prime(prev, role).to_numpy(dtype=float),
                                index=prev.mlbam_id).reindex(ids).fillna(0.0)
    hist = ps[ps.season.between(target - 3, target - 1)].copy()
    hist["pa_prime"] = pa_prime(hist, role).to_numpy(dtype=float)
    hist = hist[hist.pa_prime >= 1]
    hy = hist.groupby("mlbam_id")["season"].nunique().reindex(ids).fillna(0).astype(int)

    return MarcelRun(pred=pred, actual=actual, ids=ids,
                     pa=pa.reindex(ids), age=age_series,
                     prior_pa=prior_pa_series, history_years=hy)


# ---------------------------------------------------------------- 6. residuals_by_bucket

def _age_bucket(a: float) -> str | None:
    if not np.isfinite(a):
        return None
    for lo, hi, name in AGE_BUCKETS:
        if (lo is None or a >= lo) and (hi is None or a <= hi):
            return name
    return None


def _pt_bucket(p: float, role: str) -> str | None:
    buckets = PT_BUCKETS_H if role == "H" else PT_BUCKETS_P
    if not np.isfinite(p):
        return None
    for lo, hi, name in buckets:
        if lo <= p <= hi:
            return name
    return None


def _history_bucket(y: int) -> str | None:
    if y <= 0:
        return None
    for lo, hi, name in HISTORY_BUCKETS:
        if (y == lo) or (name == "3+" and y >= 3):
            return name
    return None


def _tier_pred_by_stat(sidecar: pd.DataFrame, target: int, role: str,
                       tier: str) -> dict[str, pd.DataFrame]:
    """Slice the predictions sidecar to one (target, role, tier). Returns {stat: DataFrame
    indexed by mlbam_id with pred_mean, q10, q50, q90}."""
    sub = sidecar[(sidecar.target == target) & (sidecar.role == role) & (sidecar.tier == tier)]
    if sub.empty:
        return {}
    out = {}
    for stat, part in sub.groupby("stat"):
        out[stat] = (part.set_index("mlbam_id")[["pred_mean", "q10", "q50", "q90"]]
                     .sort_index())
    return out


def _tier_covered(q10: np.ndarray, q90: np.ndarray, actual: np.ndarray) -> np.ndarray:
    ok = np.isfinite(q10) & np.isfinite(q90) & np.isfinite(actual)
    return np.where(ok, (actual >= q10) & (actual <= q90), np.nan).astype(float)


def build_residuals_by_bucket(runs: dict[tuple[int, str], MarcelRun],
                              sidecar: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per (tier, role, target, stat, age_bucket, pt_bucket, history_bucket). Marcel is
    always included; Tier 2/3 rows are added whenever the sidecar carries a matching prediction
    for the (target, role, stat, mlbam_id)."""
    rows: list[dict] = []
    for (target, role), r in runs.items():
        if r is None:
            continue
        w = r.pa.to_numpy()
        buckets = pd.DataFrame({
            "age_bucket": [_age_bucket(a) for a in r.age.to_numpy()],
            "pt_bucket": [_pt_bucket(p, role) for p in r.prior_pa.to_numpy()],
            "history_bucket": [_history_bucket(int(h)) for h in r.history_years.to_numpy()],
        }, index=r.ids)
        tier_stats: dict[str, dict[str, pd.DataFrame]] = {"marcel": {
            stat: pd.DataFrame({"pred_mean": r.pred[stat], "q10": np.nan, "q50": np.nan,
                                "q90": np.nan}, index=r.ids) for stat in STATS[role]}}
        if sidecar is not None:
            for tier in ("tier2", "tier3"):
                by_stat = _tier_pred_by_stat(sidecar, target, role, tier)
                if by_stat:
                    tier_stats[tier] = by_stat
        for tier, by_stat in tier_stats.items():
            for stat, pred_df in by_stat.items():
                if stat not in STATS[role]:
                    continue                              # sidecar stage_* rows (partial runs)
                pred = pred_df["pred_mean"].reindex(r.ids).to_numpy(dtype=float)
                q10 = pred_df["q10"].reindex(r.ids).to_numpy(dtype=float)
                q90 = pred_df["q90"].reindex(r.ids).to_numpy(dtype=float)
                actual = r.actual[stat].to_numpy(dtype=float)
                e = pred - actual
                cov = _tier_covered(q10, q90, actual)
                df = pd.DataFrame({"e": e, "w": w, "cov": cov,
                                   **buckets.to_dict(orient="series")})
                df = df.dropna(subset=["age_bucket", "pt_bucket", "history_bucket"])
                df = df[np.isfinite(df.e) & np.isfinite(df.w) & (df.w > 0)]
                g = df.groupby(["age_bucket", "pt_bucket", "history_bucket"], observed=True)
                for keys, part in g:
                    ww = part.w / part.w.sum()
                    covered = part["cov"].dropna()
                    rows.append({"tier": tier, "role": role, "target": target, "stat": stat,
                                 "age_bucket": keys[0], "pt_bucket": keys[1],
                                 "history_bucket": keys[2],
                                 "n": int(len(part)),
                                 "mean_error": float((ww * part.e).sum()),
                                 "rmse": float(np.sqrt((ww * part.e ** 2).sum())),
                                 "cov80": float(covered.mean()) if len(covered) else None})
    return pd.DataFrame(rows).sort_values(
        ["role", "stat", "target", "tier", "age_bucket", "pt_bucket", "history_bucket"]
    ).reset_index(drop=True)


# ---------------------------------------------------------------- 7. pit_histograms (Marcel)

def _normal_cdf(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def _piecewise_pit(actual: np.ndarray, q10: np.ndarray, q50: np.ndarray,
                   q90: np.ndarray) -> np.ndarray:
    """PIT approximated from three quantiles: linear between anchors (0.10, 0.50, 0.90); actuals
    outside [q10, q90] are pushed to the mid-tail (0.05 / 0.95). Not the true posterior-predictive
    PIT — that would need per-draw arrays — but close enough to spot calibration bias."""
    with np.errstate(divide="ignore", invalid="ignore"):
        pit = np.full_like(actual, np.nan, dtype=float)
        ok = np.isfinite(actual) & np.isfinite(q10) & np.isfinite(q50) & np.isfinite(q90)
        below = ok & (actual < q10)
        above = ok & (actual > q90)
        mid_low = ok & (actual >= q10) & (actual <= q50)
        mid_high = ok & (actual > q50) & (actual <= q90)
        pit[below] = 0.05
        pit[above] = 0.95
        d_lo = np.where(q50 - q10 > 0, q50 - q10, np.nan)
        d_hi = np.where(q90 - q50 > 0, q90 - q50, np.nan)
        pit[mid_low] = 0.10 + 0.40 * (actual[mid_low] - q10[mid_low]) / d_lo[mid_low]
        pit[mid_high] = 0.50 + 0.40 * (actual[mid_high] - q50[mid_high]) / d_hi[mid_high]
    return np.clip(pit, 0.0, 1.0)


def _pit_histogram_rows(role: str, stat: str, tier: str, pit: np.ndarray, note: str,
                        scale: float | None = None) -> list[dict]:
    edges = np.linspace(0.0, 1.0, 11)
    clean = pit[np.isfinite(pit)]
    counts, _ = np.histogram(clean, bins=edges)
    density = counts / max(counts.sum(), 1)
    return [{"role": role, "stat": stat, "tier": tier,
             "bin_lo": round(float(edges[i]), 2),
             "bin_hi": round(float(edges[i + 1]), 2),
             "count": int(counts[i]),
             "density": float(density[i]),
             "scale": scale,
             "note": note} for i in range(10)]


def build_pit_histograms(runs: dict[tuple[int, str], MarcelRun],
                         sidecar: pd.DataFrame | None = None) -> pd.DataFrame:
    """Marcel PIT via a normal approximation. When the sidecar is present, also emit a
    piecewise-linear PIT for tier2/tier3 rows using the stored q10/q50/q90."""
    rows: list[dict] = []
    pooled: dict[tuple[str, str], list[tuple[np.ndarray, np.ndarray]]] = {}
    tier_pooled: dict[tuple[str, str, str], list[np.ndarray]] = {}
    for (target, role), r in runs.items():
        if r is None:
            continue
        for stat in STATS[role]:
            e = r.pred[stat].to_numpy() - r.actual[stat].to_numpy()
            w = r.pa.to_numpy()
            ok = np.isfinite(e) & np.isfinite(w) & (w > 0)
            pooled.setdefault((role, stat), []).append((e[ok], w[ok]))
        if sidecar is None:
            continue
        for tier in ("tier2", "tier3"):
            by_stat = _tier_pred_by_stat(sidecar, target, role, tier)
            if not by_stat:
                continue
            for stat, pred_df in by_stat.items():
                if stat not in STATS[role]:
                    continue
                actual = r.actual[stat].reindex(pred_df.index).to_numpy(dtype=float)
                q10 = pred_df["q10"].to_numpy(dtype=float)
                q50 = pred_df["q50"].to_numpy(dtype=float)
                q90 = pred_df["q90"].to_numpy(dtype=float)
                pit = _piecewise_pit(actual, q10, q50, q90)
                tier_pooled.setdefault((role, stat, tier), []).append(pit)
    for (role, stat), parts in pooled.items():
        e_all = np.concatenate([p[0] for p in parts])
        w_all = np.concatenate([p[1] for p in parts])
        if e_all.size < 20:
            continue
        scale = float(np.sqrt(np.sum(w_all * e_all ** 2) / np.sum(w_all)))
        if scale <= 0 or not np.isfinite(scale):
            continue
        pit = _normal_cdf(-e_all / scale)
        rows.extend(_pit_histogram_rows(role, stat, "marcel", pit,
                                         "normal approx from pooled residuals", scale))
    for (role, stat, tier), parts in tier_pooled.items():
        pit_all = np.concatenate(parts)
        if np.isfinite(pit_all).sum() < 20:
            continue
        rows.extend(_pit_histogram_rows(role, stat, tier, pit_all,
                                         "piecewise-linear from sidecar q10/q50/q90"))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 8. biggest_misses (Marcel)

def build_biggest_misses(runs: dict[tuple[int, str], MarcelRun], b: Bundle,
                         sidecar: pd.DataFrame | None = None, k: int = 40) -> pd.DataFrame:
    people = b.people.set_index("mlbam_id")
    rows: list[dict] = []
    for (target, role), r in runs.items():
        if r is None:
            continue
        stat = KEY_STAT[role]
        actual = r.actual[stat]
        for tier, pred_df in _misses_pred_map(r, stat, sidecar, target, role).items():
            joined = pred_df.copy()
            joined["actual"] = actual.reindex(joined.index)
            joined["abs_err"] = (joined["pred"] - joined["actual"]).abs()
            joined["age"] = r.age.reindex(joined.index)
            joined["prior_pa"] = r.prior_pa.reindex(joined.index)
            joined["target_pa"] = r.pa.reindex(joined.index)
            joined = (joined.dropna(subset=["pred", "actual"])
                            .sort_values("abs_err", ascending=False).head(k))
            joined["mlbam_id"] = joined.index
            joined["name"] = joined.mlbam_id.map(people.get("name", pd.Series(dtype=object)))
            joined["role"] = role
            joined["tier"] = tier
            joined["target"] = target
            joined["stat"] = stat
            rows.extend(joined[["target", "role", "tier", "stat", "mlbam_id", "name", "age",
                                "prior_pa", "target_pa", "pred", "actual", "q10", "q90"]]
                        .to_dict(orient="records"))
    return pd.DataFrame(rows)


def _misses_pred_map(r: MarcelRun, stat: str, sidecar: pd.DataFrame | None,
                     target: int, role: str) -> dict[str, pd.DataFrame]:
    """{tier: DataFrame indexed by mlbam_id with columns pred, q10, q90}. Marcel always present;
    Tier 2/3 added when the sidecar carries a matching stat."""
    out: dict[str, pd.DataFrame] = {"marcel": pd.DataFrame({
        "pred": r.pred[stat], "q10": np.nan, "q90": np.nan}, index=r.ids)}
    if sidecar is None:
        return out
    for tier in ("tier2", "tier3"):
        by_stat = _tier_pred_by_stat(sidecar, target, role, tier)
        if stat in by_stat:
            df = by_stat[stat]
            out[tier] = pd.DataFrame({"pred": df["pred_mean"],
                                      "q10": df["q10"], "q90": df["q90"]}, index=df.index)
    return out


# ---------------------------------------------------------------- 9. stage_correlations

def build_stage_correlations(b: Bundle, window_end: int) -> pd.DataFrame:
    """Per-player residual stage rates across the last window; correlate stages within role.
    Residual = observed rate - that season's league rate (to strip out the run environment).
    PA-weighted mean over the window per (player, stage). Uses players with PA' >= 100 total."""
    rows: list[dict] = []
    for role in ROLES:
        stages = ROLE_STAGES[role]
        ps = b.ps[role]
        w0, w1 = window_end - C.WINDOW_LEN + 1, window_end
        window_ps = ps[ps.season.between(w0, w1) & ps.age.notna()]
        if window_ps.empty:
            continue
        long = stage_counts(window_ps, role)
        lg = b.lg[role].set_index(["season", "stage"]).rate
        long["lg_rate"] = long.set_index(["season", "stage"]).index.map(lg).to_numpy()
        long["resid"] = np.where(long.n > 0, long.y / np.where(long.n > 0, long.n, 1), np.nan) \
                       - long.lg_rate.astype(float)
        long["w"] = long.n.astype(float)
        agg = long.groupby(["mlbam_id", "stage"]).apply(
            lambda d: (d["resid"] * d["w"]).sum() / max(d["w"].sum(), 1.0)
            if d["w"].sum() > 0 else np.nan, include_groups=False)
        wide = agg.unstack("stage")
        pa_sum = window_ps.assign(pa=pa_prime(window_ps, role).to_numpy()) \
                          .groupby("mlbam_id")["pa"].sum()
        keep = pa_sum[pa_sum >= 100].index
        wide = wide.reindex(keep).dropna(how="any")
        if wide.empty:
            continue
        wide = wide[[s for s in stages if s in wide.columns]]
        corr = wide.corr()
        for a in corr.index:
            for c in corr.columns:
                rows.append({"role": role, "stage_a": a, "stage_b": c,
                             "corr": float(corr.loc[a, c]),
                             "n_players": int(len(wide))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 10. pt_summary

def build_pt_summary(b: Bundle, window_end: int) -> pd.DataFrame:
    """Marcel PT vs actual PA/IP by age + prior-PT bucket. Uses target = window_end - 1 so a
    complete season is scored (2026 is still in progress). Also reports the share of projected
    players with 0 PA/IP in the target season."""
    rows: list[dict] = []
    target = window_end - 1
    ages = mlb_api.season_age(b.people.set_index("mlbam_id")["birth_date"], target)
    for role in ROLES:
        ps = b.ps[role]
        train_ps = ps[ps.season < target]
        pt = MARCEL.marcel_playing_time(train_ps, role, target)
        pt = pt[pt > 0]
        actual_df = ps[ps.season == target].set_index("mlbam_id")
        actual = (actual_df.plateAppearances.astype(float) if role == "H"
                  else actual_df.outs.astype(float) / 3.0)
        merged = pd.DataFrame({"pt": pt}).join(
            pd.DataFrame({"actual": actual}), how="left")
        merged["actual"] = merged["actual"].fillna(0.0)
        merged["age"] = merged.index.map(ages).astype(float)
        # prior PT: last complete season within a 2-season lookback (mirrors Marcel's own weighting)
        prev = ps[ps.season == target - 1].set_index("mlbam_id")
        prior = (prev.plateAppearances.astype(float) if role == "H"
                 else prev.outs.astype(float) / 3.0)
        merged["prior_pt"] = merged.index.map(prior).astype(float).fillna(0.0)
        merged["age_bucket"] = merged.age.map(_age_bucket)
        merged["pt_bucket"] = merged.prior_pt.map(lambda v: _pt_bucket(v, role))
        merged["e"] = merged["pt"] - merged["actual"]
        merged["zero_actual"] = merged["actual"] <= 0
        for (age_b, pt_b), part in merged.dropna(subset=["age_bucket", "pt_bucket"]) \
                                        .groupby(["age_bucket", "pt_bucket"], observed=True):
            rows.append({"role": role, "target": target,
                         "age_bucket": age_b, "pt_bucket": pt_b,
                         "n": int(len(part)),
                         "mean_pt": float(part.pt.mean()),
                         "mean_actual": float(part.actual.mean()),
                         "mean_error": float(part.e.mean()),
                         "rmse": float(np.sqrt((part.e ** 2).mean())),
                         "share_zero_actual": float(part.zero_actual.mean())})
        # role-level totals row
        rows.append({"role": role, "target": target,
                     "age_bucket": "ALL", "pt_bucket": "ALL",
                     "n": int(len(merged)),
                     "mean_pt": float(merged.pt.mean()),
                     "mean_actual": float(merged.actual.mean()),
                     "mean_error": float(merged.e.mean()),
                     "rmse": float(np.sqrt((merged.e ** 2).mean())),
                     "share_zero_actual": float(merged.zero_actual.mean())})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 11. code_map

def build_code_map(backend_dir: Path) -> str:
    root = backend_dir / "keystone"
    lines = ["# code_map — one line per backend file",
             "",
             f"generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
             ""]
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(backend_dir)
        purpose, keys = _summarise_py(path)
        line = f"- `{rel}` — {purpose}"
        if keys:
            line += f"  (key: {', '.join(keys[:6])})"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _summarise_py(path: Path) -> tuple[str, list[str]]:
    text = path.read_text()
    doc = ""
    if text.startswith('"""'):
        end = text.find('"""', 3)
        if end > 3:
            doc = text[3:end].strip().split("\n", 1)[0].strip()
    keys: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("def "):
            name = s.split("(", 1)[0][4:].strip()
            if not name.startswith("_"):
                keys.append(name + "()")
        elif s.startswith("class "):
            name = s.split(":", 1)[0][6:].split("(", 1)[0].strip()
            keys.append(name)
    return (doc or "(no docstring)"), keys


# ---------------------------------------------------------------- 12. CONTEXT.md

def build_context_md(bt: dict, meta: dict, b: Bundle, counts: dict,
                     sidecar_state: str = "missing") -> str:
    stages_meta = meta.get("stages") or {}
    prod = meta.get("production_tier") or {}
    coverage = _data_coverage_table(b)
    gates = _gates_summary(bt)
    posterior_rows = _posterior_pretty(stages_meta)
    hit_hr = stages_meta.get("H/hr", {})
    p_hr = stages_meta.get("P/hr", {})
    hit_bip_h = stages_meta.get("H/hit_bip", {})
    hit_bip_p = stages_meta.get("P/hit_bip", {})

    # Locked-config toggles read from meta (falls back to legacy pre-M2 wording if missing).
    cfg = meta.get("model_config") or {}
    obs_noise_on = bool(cfg.get("obs_noise"))
    env_mode = cfg.get("env_mode", "mean3")
    holdout_target = bt.get("holdout_target")
    holdout_rows = [r for r in (bt.get("rows") or [])
                    if r.get("target") == holdout_target and r.get("stat") != "_diagnostics"]
    holdout_spent = holdout_target is not None and len(holdout_rows) > 0
    if holdout_spent:
        holdout_line = (f"Holdout {holdout_target} is **SPENT** (locked-config run, one-shot);"
                        f" scored rows live in `backtest.json`.")
    elif holdout_target is not None:
        holdout_line = f"Holdout {holdout_target} target is set but no scored rows on disk."
    else:
        holdout_line = "Holdout 2025 is unspent — see STATUS.md before running."

    eq_lines = [
        "theta[i, first] = lam * z(log PA'_first) + sigma_pop * e",
        "theta[i, t]     = theta[i, t-1] + g[age[i, t]] + tau * e",
    ]
    if obs_noise_on:
        eq_lines.append(
            "y[i, t]         ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t]"
            " + X_park . phi + sigma_obs * eps))")
    else:
        eq_lines.append(
            "y[i, t]         ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t]"
            " + X_park . phi))")

    prior_lines = [
        "Priors: tau ~ HalfNormal(.3), sigma_pop ~ HalfNormal(1), lam ~ N(0, .5),",
        "        g0 ~ N(0, .1), g_step_sd ~ HalfNormal(.02), park_sd ~ HalfNormal(.1),",
        "        phi ~ N(0, 1) * park_sd. Non-centred parameterisation, nutpie sampler.",
    ]
    if obs_noise_on:
        prior_lines.append(
            "        sigma_obs ~ HalfNormal(.2), non-persistent (never enters the walk).")
    if env_mode == "shock":
        prior_lines.append(
            "Projection-time env shock: per posterior draw, one N(0, sigma_env) shift shared")
        prior_lines.append(
            "across players and horizons (sigma_env = sd of yoy league logit changes).")

    lines = [
        "# KEYSTONE — Fable context pack",
        "",
        f"generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')} · "
        f"artifacts window_end: {meta.get('window_end')} · projection_season: "
        f"{meta.get('projection_season')} · production_tier: H={prod.get('H')} P={prod.get('P')}"
        f" · model_config: obs_noise={obs_noise_on} env_mode={env_mode}",
        "",
        "## 1. What KEYSTONE is (one paragraph)",
        "",
        "Bayesian component-based MLB player projection system: seven binomial stages per PA'",
        "chain (k, bb, hbp, hr, hit_bip, xbh, triple for hitters; the first five for pitchers).",
        "Marcel is Tier 1; a non-centred hierarchical state-space model per (role, stage) is",
        "Tier 2 (aging g[age], talent-drift tau, transient season noise sigma_obs, park effects",
        "on batted-ball stages, and a common league-environment shock at projection time);",
        "Statcast contact-quality indicators plug into three stages as Tier 3. Playing time is",
        "a separate Bayesian hurdle model (M3, `models/playing_time.py`): P(plays) × E[PT|plays]",
        "with a talent covariate, feeding p_play / pt_expected / p_regular per horizon into the",
        "projection artifacts. Stages are fitted independently and combined index-by-index into",
        "derived stats via a verified formula shared by actuals, projections and simulations.",
        "Frontend is React + Recharts served read-only by FastAPI over parquet + JSON artifacts.",
        "",
        "## 2. Model equations (MANUAL.md §5.3, locked config obs_noise + env shock)",
        "",
        "```",
        *eq_lines,
        "```",
        *prior_lines,
        "Tier 3 adds a second Binomial on the same theta with (barrels/BBE, ev95plus/BBE).",
        "Projections use park-aware draws for park stages (M1); the shipped h=1 median is",
        "Marcel-anchored (§6 fallback) because Tier 2 didn't clear the point-projection gate.",
        "",
        "## 3. Production tier and gate results",
        "",
        gates,
        "",
        f"Gate rule (§6): key stat is wOBA (H) / FIP (P). Tier 2 ships if RMSE <= Marcel in",
        f"3 of 4 dev targets AND mean 80% coverage in [0.75, 0.85]. Tier 3 ships if it clears",
        f"the same bar vs Tier 2. If Tier 2 fails, production is **Marcel points + Tier 2",
        f"bands** and the Methodology page says so plainly. {holdout_line}",
        "",
        "## 4. Data coverage",
        "",
        coverage,
        "",
        "## 5. Known findings and open questions",
        "",
        f"- **Hitter HR% is where Tier 2 loses.** RMSE .0155 vs Marcel .0124 (worst stat),",
        f"  cov80 .71. wHR = 2.05 is the largest wOBA weight, so hitter HR% alone plausibly",
        f"  explains the wOBA gap. Two candidate causes are laid out for Fable M1 in STATUS.md:",
        f"  (a) park-neutral scoring while Marcel is park-blind but inherits parks implicitly;",
        f"  (b) over-shrinkage from a fitting population dominated by part-timers.",
        f"- **H/hit_bip divergence concentration.** 181 of 313 total dev divergences at",
        f"  target_accept 0.9 come from this one stage. The verified simulation had 0",
        f"  divergences at the same scale, so it is real-data structure the non-centred",
        f"  parameterisation does not absorb — most likely a funnel where sigma_pop = "
        f"{hit_bip_h.get('sigma_pop_mean', 0):.3f} is small next to binomial noise. Tier 3",
        f"  target_accept 0.95 collapsed this to ~4 divergences per fit.",
        f"- **DIPS falls out of the fit.** sigma_pop for hit_bip: H {hit_bip_h.get('sigma_pop_mean', 0):.3f}",
        f"  vs P {hit_bip_p.get('sigma_pop_mean', 0):.3f} (~ 2x wider talent spread for hitters).",
        f"- **HR park effects, H stage.** park_sd_mean {hit_hr.get('park_sd_mean', 0):.3f}",
        f"  (~35% logit swing between top and bottom parks); see park_effects.csv.",
        f"- **Sampling health at production.** max r_hat {meta.get('max_rhat')}, total",
        f"  divergences {meta.get('total_divergences')} across 12 fits (better than dev; still",
        f"  P/k 1.11 and P/hr 1.10 above the 1.05 line).",
        "",
        "## 6. Population parameters (window_end fits from meta.json)",
        "",
        posterior_rows,
        "",
        "## 7. What is in this pack (and what is not)",
        "",
        "Each CSV is capped at 2,000 rows; this file is capped at 400 lines.",
        "",
        "| file | rows | source | notes |",
        "|---|---:|---|---|",
        f"| backtest_summary.csv | {counts['backtest_summary']} | data/artifacts/backtest.json | complete |",
        f"| posterior_summaries.csv | {counts['posterior_summaries']} | meta.json + backtest diag rows + sidecar (M1) | sidecar {sidecar_state} |",
        f"| aging_curves.csv | {counts['aging_curves']} | data/artifacts/aging.parquet | mean only; q10/q90 need per-draw sidecar |",
        f"| park_effects.csv | {counts['park_effects']} | meta.json top/bottom_hr_parks | phi_sd null; only top/bottom 3 for hr; other park stages absent |",
        f"| residuals_by_bucket.csv | {counts['residuals_by_bucket']} | Marcel vs actuals + sidecar Tier 2/3 (M1) | sidecar {sidecar_state} |",
        f"| pit_histograms.csv | {counts['pit_histograms']} | Marcel normal approx + sidecar piecewise Tier 2/3 (M1) | sidecar {sidecar_state} |",
        f"| biggest_misses.csv | {counts['biggest_misses']} | Marcel + sidecar Tier 2/3 key-stat errors (M1) | sidecar {sidecar_state} |",
        f"| stage_correlations.csv | {counts['stage_correlations']} | observed residual rates in last window | proxy for talent correlation; not from posteriors |",
        f"| pt_summary.csv | {counts['pt_summary']} | Marcel PT vs actual for target={meta.get('window_end') - 1 if meta.get('window_end') else '-'} | includes share_zero_actual |",
        f"| code_map.md | 1 per file | walk of backend/keystone/ | |",
        "",
        "### Sidecar (M1)",
        "",
        "`backtest_predictions.parquet` (target, role, tier, mlbam_id, stat, pred_mean, q10, q50,",
        "q90) and `backtest_posteriors.parquet` (target, role, tier, stage, tau_mean, tau_sd,",
        "sigma_pop_*, lam_*, sigma_age_*, park_sd_*, ess_bulk_min, max_rhat, divergences) are",
        f"written next to backtest.json on every `make backtest`. Current status: **{sidecar_state}**.",
        "When present, the sidecar fills the Tier 2/3 columns of the tables above; when absent,",
        "diagnostics falls back to Marcel-only rows so `make diagnostics` never fails.",
        "",
        "## 8. Pointers into the code",
        "",
        "- Stage math & derivations: `backend/keystone/components.py` (verified reference)",
        "- Marcel: `backend/keystone/models/marcel.py`",
        "- Tier 2/3 model + projection: `backend/keystone/models/state_space.py`",
        "- League environment: `backend/keystone/league.py`",
        "- Backtest harness + gates: `backend/keystone/eval/backtest.py`",
        "- Production artifacts: `backend/keystone/project.py`",
        "- Statcast indicators: `backend/keystone/data/statcast.py`",
        "- CLI: `backend/keystone/pipeline.py`",
        "- Full file map: see `code_map.md` in this directory.",
        "",
        "## 9. Rules of the road (from FABLE_MISSIONS.md §4)",
        "",
        "- One session per mission; don't clear mid-mission.",
        "- Think deep, write compact. Targeted edits, not file rewrites. No printing dataframes.",
        "- Long compute belongs to Daniel; validate with `--quick`, put full runs in STATUS.md.",
        "- No tuning on 2025. Pre-register every hypothesis before Daniel's run.",
        "- Mechanical work → docs/fable/HANDOFF.md, one checkbox each with file + change + check.",
    ]
    return _clip_lines(lines, MAX_CONTEXT_LINES)


def _clip_lines(lines: list[str], cap: int) -> str:
    if len(lines) <= cap:
        return "\n".join(lines) + "\n"
    kept = lines[:cap - 1] + [f"<!-- clipped: {len(lines) - cap + 1} more lines -->"]
    return "\n".join(kept) + "\n"


def _data_coverage_table(b: Bundle) -> str:
    lines = ["| season | H rows | P rows | H PA' total | P BF' total |",
             "|---:|---:|---:|---:|---:|"]
    seasons = sorted(set(b.ps["H"].season.unique().tolist()) | set(b.ps["P"].season.unique().tolist()))
    for s in seasons:
        h = b.ps["H"][b.ps["H"].season == s]
        p = b.ps["P"][b.ps["P"].season == s]
        h_pa = int(pa_prime(h, "H").sum()) if not h.empty else 0
        p_pa = int(pa_prime(p, "P").sum()) if not p.empty else 0
        lines.append(f"| {s} | {len(h)} | {len(p)} | {h_pa:,} | {p_pa:,} |")
    return "\n".join(lines)


def _gates_summary(bt: dict) -> str:
    gates = bt.get("gates") or {}
    if not gates:
        return "_no gates recorded._"
    lines = ["| role | tier | wins | of | need | cov80_mean | vs | pass |",
             "|---|---|---:|---:|---:|---:|---|---|"]
    for role, per_tier in gates.items():
        for tier, g in (per_tier or {}).items():
            if not g:
                continue
            cov = g.get("cov80_mean")
            lines.append(f"| {role} | {tier} | {g.get('wins')} | {g.get('of')} | "
                         f"{g.get('need')} | {round(cov, 3) if cov is not None else '-'} | "
                         f"{g.get('vs')} | {'PASS' if g.get('pass') else 'FAIL'} |")
    return "\n".join(lines)


def _posterior_pretty(stages_meta: dict) -> str:
    lines = ["| role/stage | tau_mean | sigma_pop_mean | park_sd_mean | max_rhat | divergences |",
             "|---|---:|---:|---:|---:|---:|"]
    for key, s in stages_meta.items():
        ps = s.get("park_sd_mean")
        lines.append(f"| {key} | {s.get('tau_mean', 0):.4f} | "
                     f"{s.get('sigma_pop_mean', 0):.4f} | "
                     f"{'-' if ps is None else f'{ps:.4f}'} | "
                     f"{s.get('max_rhat')} | {s.get('divergences')} |")
    return "\n".join(lines)


# ---------------------------------------------------------------- entry point

def run(out: Path, artifacts_dir: Path | None = None, processed_dir: Path | None = None,
        backend_dir: Path | None = None) -> None:
    artifacts_dir = Path(artifacts_dir or C.ARTIFACTS)
    processed_dir = Path(processed_dir or C.PROCESSED)
    backend_dir = Path(backend_dir or (C.REPO_ROOT / "backend"))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[diagnostics] out={out}  artifacts={artifacts_dir}  processed={processed_dir}")

    bt = _load_json(artifacts_dir / "backtest.json")
    meta = _load_json(artifacts_dir / "meta.json")
    if not bt:
        raise SystemExit(f"[diagnostics] missing {artifacts_dir/'backtest.json'} — run `make backtest`")
    if not meta:
        raise SystemExit(f"[diagnostics] missing {artifacts_dir/'meta.json'} — run `make project`")

    preds_sidecar = _load_parquet(artifacts_dir / "backtest_predictions.parquet")
    posts_sidecar = _load_parquet(artifacts_dir / "backtest_posteriors.parquet")
    sidecar_state = "present" if preds_sidecar is not None else "missing"
    print(f"[diagnostics] backtest sidecar: {sidecar_state}")

    b = load_bundle(processed_dir)

    # Marcel per-target predictions (cheap: no fits).
    runs: dict[tuple[int, str], MarcelRun] = {}
    dev_targets = [t for t in bt.get("targets", []) if t != C.HOLDOUT_TARGET]
    for target in dev_targets:
        for role in ROLES:
            print(f"[diagnostics] Marcel predictions {role} {target}")
            runs[(target, role)] = _marcel_target(b, role, target)

    frames = {
        "backtest_summary.csv": build_backtest_summary(bt),
        "posterior_summaries.csv": build_posterior_summaries(bt, meta, posts_sidecar),
        "aging_curves.csv": build_aging_curves(artifacts_dir),
        "park_effects.csv": build_park_effects(meta),
        "residuals_by_bucket.csv": build_residuals_by_bucket(runs, preds_sidecar),
        "pit_histograms.csv": build_pit_histograms(runs, preds_sidecar),
        "biggest_misses.csv": build_biggest_misses(runs, b, preds_sidecar),
        "stage_correlations.csv": build_stage_correlations(b, meta.get("window_end") or C.SEASON_END),
        "pt_summary.csv": build_pt_summary(b, meta.get("window_end") or C.SEASON_END),
    }
    counts = {name.replace(".csv", ""): _write_csv(df, out / name, CAP_OVERRIDES.get(name, CAP_ROWS))
              for name, df in frames.items()}

    (out / "code_map.md").write_text(build_code_map(backend_dir))
    ctx = build_context_md(bt, meta, b, counts, sidecar_state)
    (out / "CONTEXT.md").write_text(ctx)

    line_count = ctx.count("\n")
    print(f"[diagnostics] wrote {len(frames)} CSVs + code_map.md + CONTEXT.md ({line_count} lines)")
    print(f"[diagnostics] row counts: " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    if line_count > MAX_CONTEXT_LINES:
        raise AssertionError(f"CONTEXT.md is {line_count} lines (cap {MAX_CONTEXT_LINES})")
    for name, df in frames.items():
        cap = CAP_OVERRIDES.get(name, CAP_ROWS)
        if len(df) > cap:      # check what was WRITTEN, not the pre-truncation frame
            raise AssertionError(f"{name} has {len(df)} rows (cap {cap}) — raise its CAP_OVERRIDE "
                                 f"or aggregate it, don't let _write_csv truncate silently")
