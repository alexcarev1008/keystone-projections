"""League-season constants. VERIFIED REFERENCE (tests: backend/tests/test_league.py).

All inputs are player-season tables with Stats API column names, summed over teams.
  * stage league rates / logits  -> computed on the MODELLED population (filtered hitters or pitchers)
  * sf_rate                      -> league SF per PA' (hitters)
  * kappa, c_fip, lg_era         -> computed on ALL pitchers (unfiltered), so league FIP == league ERA
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from keystone.components import stage_counts


def stage_league_rates(df: pd.DataFrame, role: str) -> pd.DataFrame:
    """Returns season, stage, y, n, rate, logit."""
    long = stage_counts(df, role)
    lg = long.groupby(["season", "stage"], as_index=False)[["y", "n"]].sum()
    lg["rate"] = lg.y / lg.n
    lg["logit"] = np.log(lg.rate / (1 - lg.rate))
    return lg


def hitter_constants(hit: pd.DataFrame) -> pd.DataFrame:
    g = hit.groupby("season")[["plateAppearances", "intentionalWalks", "sacBunts", "catchersInterference", "sacFlies"]].sum()
    pa_prime = g.plateAppearances - g.intentionalWalks - g.sacBunts - g.catchersInterference
    return pd.DataFrame({"sf_rate": g.sacFlies / pa_prime}).reset_index()


def pitcher_constants(pit_all: pd.DataFrame) -> pd.DataFrame:
    cols = ["battersFaced", "intentionalWalks", "sacBunts", "catchersInterference", "baseOnBalls",
            "hitBatsmen", "hits", "homeRuns", "strikeOuts", "outs", "earnedRuns"]
    g = pit_all.groupby("season")[cols].sum()
    bf_prime = g.battersFaced - g.intentionalWalks - g.sacBunts - g.catchersInterference
    ubb = g.baseOnBalls - g.intentionalWalks
    ip = g.outs / 3
    kappa = g.outs / (bf_prime - ubb - g.hitBatsmen - g.hits)
    lg_era = 9 * g.earnedRuns / ip
    c_fip = lg_era - (13 * g.homeRuns + 3 * (ubb + g.hitBatsmen) - 2 * g.strikeOuts) / ip
    return pd.DataFrame({"kappa": kappa, "lg_era": lg_era, "c_fip": c_fip}).reset_index()


def projection_logit(lg_rates: pd.DataFrame, stage: str, window_end: int, n_years: int = 3) -> float:
    """League environment assumed for projections: mean logit of the last n_years seasons in the window."""
    sel = lg_rates[(lg_rates.stage == stage) & lg_rates.season.between(window_end - n_years + 1, window_end)]
    return float(sel.logit.mean())


def projection_logit_recency(lg_rates: pd.DataFrame, stage: str, window_end: int,
                             n_years: int = 3, vol_years: int = 6) -> tuple[float, float]:
    """M2a E2: (mu, sigma_env) league-environment forecast for window_end + 1.

    mu = mean logit of the last n_years, weighted by recency (1..n_years) x season trial share
    (so 2020 self-downweights). sigma_env = sd of year-over-year logit changes across the last
    vol_years seasons — the missing common forecast-error term for projection intervals.
    """
    df = lg_rates[lg_rates.stage == stage].drop_duplicates("season").sort_values("season")
    sel = df[df.season.between(window_end - n_years + 1, window_end)]
    if sel.empty:
        raise ValueError(f"no league rates for stage {stage} up to {window_end}")
    rec = sel.season - (window_end - n_years)                # 1 .. n_years
    w = rec.to_numpy(dtype=float) * sel.n.to_numpy(dtype=float) / sel.n.max()
    mu = float(np.average(sel.logit.to_numpy(), weights=w))
    vol = df[df.season.between(window_end - vol_years + 1, window_end)]
    diffs = vol.logit.diff().dropna()
    sigma_env = float(diffs.std(ddof=1)) if len(diffs) >= 2 else 0.0
    return mu, sigma_env
