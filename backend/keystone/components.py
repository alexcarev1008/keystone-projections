"""Component ("stage") definitions and deterministic derivations.

VERIFIED REFERENCE (tests: backend/tests/test_components.py). Extend, don't rewrite.

Every plate appearance is decomposed into a chain of conditional binomial stages.
Because each stage's trials are what is left after the previous stage, projected
counts always sum back to the PA total, and every stage is a proper binomial
rate the hierarchical model can shrink by its own reliability.

    PA' = PA - IBB - SH - CI                (the wOBA denominator: AB + uBB + HBP + SF)
    k        K            / PA'
    bb       uBB          / (PA' - K)
    hbp      HBP          / (PA' - K - uBB)
    hr       HR           / (PA' - K - uBB - HBP)          (HR per contact PA)
    hit_bip  H - HR       / (PA' - K - uBB - HBP - HR)     (== BABIP exactly)
    xbh      2B + 3B      / (H - HR)                        (hitters only)
    triple   3B           / (2B + 3B)                       (hitters only)

Pitchers use the same first five stages on BF' = BF - IBB - SH - CI.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HITTER_STAGES = ["k", "bb", "hbp", "hr", "hit_bip", "xbh", "triple"]
PITCHER_STAGES = ["k", "bb", "hbp", "hr", "hit_bip"]
# Stages where the ballpark is allowed to matter (batted-ball outcomes only).
PARK_STAGES = {"hr", "hit_bip", "xbh", "triple"}


def stage_counts(df: pd.DataFrame, role: str) -> pd.DataFrame:
    """Return long table: one row per (input row, stage) with columns stage, y, n.

    Required input columns (MLB Stats API names, already summed over teams):
      hitters : plateAppearances, baseOnBalls, intentionalWalks, hitByPitch, strikeOuts,
                sacBunts, catchersInterference, hits, doubles, triples, homeRuns
      pitchers: battersFaced, baseOnBalls, intentionalWalks, hitBatsmen, strikeOuts,
                sacBunts, catchersInterference, hits, homeRuns
    """
    if role == "H":
        pa = df.plateAppearances - df.intentionalWalks - df.sacBunts - df.catchersInterference
        hbp = df.hitByPitch
    elif role == "P":
        pa = df.battersFaced - df.intentionalWalks - df.sacBunts - df.catchersInterference
        hbp = df.hitBatsmen
    else:
        raise ValueError(role)
    ubb = df.baseOnBalls - df.intentionalWalks
    k = df.strikeOuts
    hr = df.homeRuns
    h_bip = df.hits - df.homeRuns
    stages = {
        "k": (k, pa),
        "bb": (ubb, pa - k),
        "hbp": (hbp, pa - k - ubb),
        "hr": (hr, pa - k - ubb - hbp),
        "hit_bip": (h_bip, pa - k - ubb - hbp - hr),
    }
    if role == "H":
        stages["xbh"] = (df.doubles + df.triples, h_bip)
        stages["triple"] = (df.triples, df.doubles + df.triples)
    out = []
    for name, (y, n) in stages.items():
        part = df.drop(columns=[c for c in df.columns if c in ("y", "n")]).copy()
        part["stage"], part["y"], part["n"] = name, y.astype(int), n.astype(int)
        out.append(part)
    long = pd.concat(out, ignore_index=True)
    if (long.y < 0).any() or (long.y > long.n).any():
        bad = long[(long.y < 0) | (long.y > long.n)].head()
        raise ValueError(f"Impossible stage counts (check column mapping):\n{bad}")
    return long


def per_pa_from_stage_rates(p: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Convert conditional stage probabilities (arrays of draws) into per-PA' event rates."""
    k = p["k"]
    bb = (1 - k) * p["bb"]
    hbp = (1 - k) * (1 - p["bb"]) * p["hbp"]
    contact = (1 - k) * (1 - p["bb"]) * (1 - p["hbp"])
    hr = contact * p["hr"]
    bip = contact * (1 - p["hr"])
    h_bip = bip * p["hit_bip"]
    out = dict(k=k, bb=bb, hbp=hbp, hr=hr, bip=bip, h_bip=h_bip)
    if "xbh" in p:
        xbh = h_bip * p["xbh"]
        out["triple"] = xbh * p["triple"]
        out["double"] = xbh - out["triple"]
        out["single"] = h_bip - xbh
    return out


def derive_hitter(p: dict[str, np.ndarray], w: dict[str, float], sf_rate: float) -> dict[str, np.ndarray]:
    """Rate stats from stage probabilities.

    w: wOBA weights for the season (keys wBB, wHBP, w1B, w2B, w3B, wHR) from data/external/fg_guts.csv.
    sf_rate: league sacrifice flies per PA' (recent 3-season mean) — SF is not modelled per player.
    OBP here excludes IBB (uBB only) — documented approximation (< .003 for almost everyone).
    """
    r = per_pa_from_stage_rates(p)
    hits = r["single"] + r["double"] + r["triple"] + r["hr"]
    ab = 1 - r["bb"] - r["hbp"] - sf_rate
    tb = r["single"] + 2 * r["double"] + 3 * r["triple"] + 4 * r["hr"]
    woba = (w["wBB"] * r["bb"] + w["wHBP"] * r["hbp"] + w["w1B"] * r["single"]
            + w["w2B"] * r["double"] + w["w3B"] * r["triple"] + w["wHR"] * r["hr"])
    avg, slg = hits / ab, tb / ab
    return dict(k_pct=r["k"], bb_pct=r["bb"], hr_pct=r["hr"], babip=p["hit_bip"],
                avg=avg, obp=hits + r["bb"] + r["hbp"], slg=slg, iso=slg - avg, woba=woba)


def derive_pitcher(p: dict[str, np.ndarray], kappa: float, c_fip: float) -> dict[str, np.ndarray]:
    """Rate stats for pitchers.

    kappa: league outs per 'non-reaching' BF' = lg_outs / (BF' - uBB - HBP - H), recent 3-season mean.
           Absorbs double plays, caught stealing, errors, sac flies.
    c_fip: league FIP constant computed with the SAME uBB-based formula (see league.py), so lg FIP == lg ERA.
    """
    r = per_pa_from_stage_rates(p)
    hits = r["hr"] + r["h_bip"]
    outs_per_bf = kappa * (1 - r["bb"] - r["hbp"] - hits)
    ip_per_bf = outs_per_bf / 3
    fip = (13 * r["hr"] + 3 * (r["bb"] + r["hbp"]) - 2 * r["k"]) / ip_per_bf + c_fip
    return dict(k_pct=r["k"], bb_pct=r["bb"], k_minus_bb=r["k"] - r["bb"], hr_pct=r["hr"],
                babip=p["hit_bip"], fip=fip, ip_per_bf=ip_per_bf)


def simulate_season(p: dict[str, np.ndarray], n_pa: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Posterior-predictive season counts given actual/projected PA' (adds binomial noise stage by stage).
    Used for interval coverage in backtests. Returns per-draw counts keyed like stage_counts."""
    k = rng.binomial(n_pa, p["k"])
    bb = rng.binomial(n_pa - k, p["bb"])
    hbp = rng.binomial(n_pa - k - bb, p["hbp"])
    hr = rng.binomial(n_pa - k - bb - hbp, p["hr"])
    h_bip = rng.binomial(n_pa - k - bb - hbp - hr, p["hit_bip"])
    out = dict(pa=np.full_like(k, n_pa), k=k, bb=bb, hbp=hbp, hr=hr, h_bip=h_bip)
    if "xbh" in p:
        xbh = rng.binomial(h_bip, p["xbh"])
        out["triple"] = rng.binomial(xbh, p["triple"])
        out["double"] = xbh - out["triple"]
        out["single"] = h_bip - xbh
    return out
