"""M4 ML challenger: HistGradientBoostingRegressor vs the locked Tier 2 (E5+E6).

Design + pre-registered rules: docs/fable/M4_ml_challenger.md (§1–§4, committed before any
run). Same information set as Tier 2: every feature comes from `train_slice(bundle, T)`,
so nothing at or after season T can enter by construction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from keystone import config as C
from keystone import league as LG
from keystone.components import pa_prime, simulate_season, stage_counts
from keystone.eval import backtest as BT

HP_A = dict(learning_rate=.06, max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0,
            max_iter=1000, early_stopping=True, validation_fraction=.15, n_iter_no_change=30,
            random_state=1)
HP_B = {**HP_A, "max_leaf_nodes": 31, "min_samples_leaf": 20}
HP_HYBRID = dict(learning_rate=.05, max_leaf_nodes=7, min_samples_leaf=30, max_iter=300,
                 early_stopping=True, validation_fraction=.2, n_iter_no_change=30,
                 random_state=1)
FIRST_LABEL_SEASON = 2016
N_CRPS_DRAWS = 500


# ---------------------------------------------------------------- feature frame

def _smoothed_dev(y, n, mu_logit):
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.log((y + 0.5) / (n + 1) / (1 - (y + 0.5) / (n + 1)))
    return z - mu_logit


def stage_table(train: BT.Bundle, role: str) -> pd.DataFrame:
    """(mlbam_id, season, stage) -> y, n, dev (smoothed logit dev from league), pa, age."""
    ps = train.ps[role]
    ps = ps[ps.age.notna()]
    long = stage_counts(ps, role)
    long["pa"] = pa_prime(long, role).to_numpy()
    lg = train.lg[role].drop_duplicates(["season", "stage"]).set_index(["season", "stage"]).logit
    mu = pd.MultiIndex.from_frame(long[["season", "stage"]]).map(lg).to_numpy(dtype=float)
    dev = _smoothed_dev(long.y.to_numpy(float), long.n.to_numpy(float), mu)
    long["dev"] = np.where(long.n.to_numpy(float) > 0, dev, np.nan)
    return long


def feature_frame(train: BT.Bundle, role: str, stage: str, seasons: list[int],
                  ids_by_season: dict[int, np.ndarray] | None = None) -> pd.DataFrame:
    """Rows = (player, season s) for s in `seasons`; every feature lag >= 1.

    ids_by_season restricts rows (projection mode); default = players with a row in s
    (training mode, labels attached by caller).
    """
    tab = stage_table(train, role)
    me = tab[tab.stage == stage].set_index(["mlbam_id", "season"])
    others = [st for st in BT.ROLE_STAGES[role] if st != stage]
    xdev = {st: tab[tab.stage == st].set_index(["mlbam_id", "season"]).dev for st in others}
    ps = train.ps[role]
    age = ps.set_index(["mlbam_id", "season"]).age
    pa_by = me.pa
    first_season = ps.groupby("mlbam_id").season.min()
    rp = None
    if role == "P":
        g = ps.gamesPitched.clip(lower=1)
        rp = pd.Series(((1.0 - ps.gamesStarted / g).clip(0, 1)).to_numpy(),
                       index=pd.MultiIndex.from_frame(ps[["mlbam_id", "season"]]))

    rows = []
    for s in seasons:
        pids = (np.asarray(ids_by_season[s]) if ids_by_season is not None
                else me.index[me.index.get_level_values("season") == s]
                     .get_level_values("mlbam_id").to_numpy())
        f = pd.DataFrame(index=pd.Index(pids, name="mlbam_id"))
        f["season"] = s
        for k in (1, 2, 3):
            mi = pd.MultiIndex.from_arrays([pids, np.full(len(pids), s - k)])
            f[f"dev_lag{k}"] = me.dev.reindex(mi).to_numpy()
            f[f"n_lag{k}"] = me.n.reindex(mi).fillna(0).to_numpy()
            f[f"pa_lag{k}"] = pa_by.reindex(mi).fillna(0).to_numpy()
        mi1 = pd.MultiIndex.from_arrays([pids, np.full(len(pids), s - 1)])
        for st in others:
            f[f"xdev_{st}_lag1"] = xdev[st].reindex(mi1).to_numpy()
        f["age"] = age.reindex(pd.MultiIndex.from_arrays(
            [pids, np.full(len(pids), s)])).to_numpy()
        if f.age.isna().any():          # projection rows: age at T = last known age + gap
            last = ps[ps.mlbam_id.isin(pids)].sort_values("season").groupby("mlbam_id").last()
            fallback = (last.age + (s - last.season)).reindex(pids).to_numpy()
            f["age"] = np.where(np.isfinite(f.age), f.age, fallback)
        f["n_hist"] = (s - first_season.reindex(pids)).clip(upper=s - 2015).fillna(0).to_numpy()
        if rp is not None:
            f["rp_share_lag1"] = rp.reindex(mi1).to_numpy()
        rows.append(f.reset_index())
    return pd.concat(rows, ignore_index=True)


def training_data(train: BT.Bundle, role: str, stage: str, last_label: int):
    seasons = list(range(FIRST_LABEL_SEASON, last_label + 1))
    X = feature_frame(train, role, stage, seasons)
    tab = stage_table(train, role)
    me = tab[tab.stage == stage].set_index(["mlbam_id", "season"])
    mi = pd.MultiIndex.from_frame(X[["mlbam_id", "season"]])
    y = me.dev.reindex(mi).to_numpy()
    w = me.n.reindex(mi).fillna(0).to_numpy(dtype=float)
    keep = np.isfinite(y) & (w > 0)
    return X[keep], y[keep], w[keep]


def fit_predict_stage(train: BT.Bundle, role: str, stage: str, target: int,
                      ids: np.ndarray, hp: dict, last_label: int | None = None) -> np.ndarray:
    """Returns predicted stage probs for `ids` at season `target`."""
    last_label = last_label or target - 1
    X, y, w = training_data(train, role, stage, last_label)
    cols = [c for c in X.columns if c not in ("mlbam_id", "season")]
    m = HistGradientBoostingRegressor(**hp)
    m.fit(X[cols], y, sample_weight=w)
    Xp = feature_frame(train, role, stage, [target], {target: ids})
    dev = m.predict(Xp[cols])
    mu = LG.projection_logit(train.lg[role], stage, target - 1)
    return 1.0 / (1.0 + np.exp(-(mu + dev)))


def gbm_probs(train: BT.Bundle, role: str, target: int, ids: np.ndarray, hp: dict,
              last_label: int | None = None) -> pd.DataFrame:
    return pd.DataFrame({st: fit_predict_stage(train, role, st, target, ids, hp, last_label)
                         for st in BT.ROLE_STAGES[role]}, index=pd.Index(ids, name="mlbam_id"))


# ---------------------------------------------------------------- distributional pieces

def s_binom(probs: pd.DataFrame, role: str, env: dict, pa: pd.Series, ip: pd.Series,
            rng) -> dict[str, np.ndarray]:
    """Aleatoric sd per (player, stat): sd of derived stats over simulated seasons at
    actual PA', from the GBM stage probs. Same values applied to every model."""
    out = {s: np.full(len(probs), np.nan) for s in BT.STATS[role]}
    for i, pid in enumerate(probs.index):
        n_pa = int(pa.loc[pid])
        ip_i = float(ip.loc[pid]) if role == "P" else None
        if n_pa <= 0 or (role == "P" and not (ip_i and ip_i > 0)):
            continue
        draws = {st: np.full(400, probs.iloc[i][st]) for st in probs.columns}
        sim = BT.stats_from_counts(simulate_season(draws, n_pa, rng), role, env, ip=ip_i)
        for s in BT.STATS[role]:
            v = np.asarray(sim[s], float)
            out[s][i] = np.nanstd(v[np.isfinite(v)])
    return out


def split_normal_draws(q10, q50, q90, n, rng):
    """Split-normal from three quantiles (M1 piecewise precedent), (players, n) draws."""
    z = 1.2815515655446004
    lo, hi = (q50 - q10) / z, (q90 - q50) / z
    lo, hi = np.maximum(lo, 1e-9), np.maximum(hi, 1e-9)
    p_hi = hi / (lo + hi)
    a = np.abs(rng.standard_normal((len(q50), n)))
    side = rng.random((len(q50), n)) < p_hi[:, None]
    return q50[:, None] + np.where(side, a * hi[:, None], -a * lo[:, None])


def crps_from_draws(draws: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Per-player CRPS, MC estimator. draws (players, n)."""
    n = draws.shape[1]
    term1 = np.mean(np.abs(draws - actual[:, None]), axis=1)
    d = np.sort(draws, axis=1)
    i = np.arange(1, n + 1)
    e_xx = 2.0 / n ** 2 * np.sum((2 * i - n - 1) * d, axis=1)   # E|X-X'|
    return term1 - 0.5 * e_xx


def dist_scores(draws: np.ndarray, actual: np.ndarray, w: np.ndarray) -> dict:
    ok = np.isfinite(actual) & np.isfinite(w) & (w > 0) & np.isfinite(draws).all(axis=1)
    d, a, ww = draws[ok], actual[ok], w[ok] / w[ok].sum()
    crps = crps_from_draws(d, a)
    q10, q90 = np.quantile(d, 0.10, axis=1), np.quantile(d, 0.90, axis=1)
    pinball = 0.5 * (np.maximum(0.1 * (a - q10), (0.1 - 1) * (a - q10)) +
                     np.maximum(0.9 * (a - q90), (0.9 - 1) * (a - q90)))
    return {"crps": float(np.sum(ww * crps)), "pinball": float(np.sum(ww * pinball)),
            "cov80": float(np.mean((q10 <= a) & (a <= q90))), "n": int(ok.sum())}


# ---------------------------------------------------------------- per-target evaluation

def eval_target(b: BT.Bundle, role: str, target: int, sidecar: pd.DataFrame, rng,
                hp=HP_A, tag="gbm"):
    train = BT.train_slice(b, target)
    env = BT.scoring_env(b, role, target)
    ids = BT.eval_population(b, role, target)
    obs_t = b.ps[role]
    obs_t = obs_t[(obs_t.season == target) & obs_t.mlbam_id.isin(ids)]
    pa = pd.Series(pa_prime(obs_t, role).to_numpy(float), index=obs_t.mlbam_id)
    ip = (pd.Series(obs_t.outs.to_numpy(float) / 3.0, index=obs_t.mlbam_id)
          if role == "P" else pd.Series(dtype=float))
    w = pa.reindex(ids).to_numpy()
    ip_v = ip.reindex(ids).to_numpy() if role == "P" else None
    ap = BT.actual_stage_probs(obs_t, role, b.lg[role], target).reindex(ids)
    actual = pd.DataFrame(BT.stats_from_stage_probs(
        {s: ap[s].to_numpy() for s in BT.ROLE_STAGES[role]}, role, env, pa=w, ip=ip_v),
        index=ids)

    # Marcel reproduction (pipeline validation) + per-player marcel stats (hybrid features)
    mz = BT.marcel_probs(train, role, target).reindex(ids)
    marcel_stats = pd.DataFrame(BT.stats_from_stage_probs(
        {s: mz[s].to_numpy(float) for s in BT.ROLE_STAGES[role]}, role, env, pa=w, ip=ip_v),
        index=ids)

    # GBM
    probs = gbm_probs(train, role, target, ids, hp)
    gbm_stats = pd.DataFrame(BT.stats_from_stage_probs(
        {s: probs[s].to_numpy() for s in BT.ROLE_STAGES[role]}, role, env, pa=w, ip=ip_v),
        index=ids)

    # aleatoric sd (shared) + epistemic sd via auxiliary fit on <= T-2 predicting T-1
    sb = s_binom(probs, role, env, pa, ip, rng)
    s_epi = {}
    prev = target - 1
    train_prev = BT.train_slice(b, prev)
    ids_prev = BT.eval_population(b, role, prev)
    obs_p = b.ps[role]
    obs_p = obs_p[(obs_p.season == prev) & obs_p.mlbam_id.isin(ids_prev)]
    pa_p = pd.Series(pa_prime(obs_p, role).to_numpy(float), index=obs_p.mlbam_id)
    ip_p = (pd.Series(obs_p.outs.to_numpy(float) / 3.0, index=obs_p.mlbam_id)
            if role == "P" else pd.Series(dtype=float))
    w_p = pa_p.reindex(ids_prev).to_numpy()
    ip_pv = ip_p.reindex(ids_prev).to_numpy() if role == "P" else None
    ap_p = BT.actual_stage_probs(obs_p, role, b.lg[role], prev).reindex(ids_prev)
    actual_p = pd.DataFrame(BT.stats_from_stage_probs(
        {s: ap_p[s].to_numpy() for s in BT.ROLE_STAGES[role]}, role, env, pa=w_p, ip=ip_pv),
        index=ids_prev)
    probs_p = gbm_probs(train_prev, role, prev, ids_prev, hp)
    stats_p = pd.DataFrame(BT.stats_from_stage_probs(
        {s: probs_p[s].to_numpy() for s in BT.ROLE_STAGES[role]}, role, env,
        pa=w_p, ip=ip_pv), index=ids_prev)
    sb_p = s_binom(probs_p, role, env, pa_p, ip_p, rng)
    for s in BT.STATS[role]:
        r = stats_p[s].to_numpy() - actual_p[s].to_numpy()
        ok = np.isfinite(r) & np.isfinite(w_p) & (w_p > 0) & np.isfinite(sb_p[s])
        ww = w_p[ok] / w_p[ok].sum()
        tot = float(np.sum(ww * r[ok] ** 2))
        s_epi[s] = float(np.sqrt(max(0.0, tot - np.sum(ww * sb_p[s][ok] ** 2))))

    # tier2 sidecar for this (target, role)
    sc = sidecar[(sidecar.target == target) & (sidecar.role == role)]
    sc = sc.pivot_table(index="mlbam_id", columns="stat",
                        values=["pred_mean", "q10", "q50", "q90"]).reindex(ids)

    rows, t2_draws_store = [], {}
    for s in BT.STATS[role]:
        a = actual[s].to_numpy()
        rows.append({"target": target, "role": role, "model": "marcel", "stat": s,
                     **BT.weighted_metrics(marcel_stats[s].to_numpy(), a, w)})
        rows.append({"target": target, "role": role, "model": tag, "stat": s,
                     **BT.weighted_metrics(gbm_stats[s].to_numpy(), a, w)})
        rows.append({"target": target, "role": role, "model": "tier2_sidecar", "stat": s,
                     **BT.weighted_metrics(sc["pred_mean"][s].to_numpy(), a, w)})
        noise = rng.standard_normal((len(ids), N_CRPS_DRAWS))
        alea = np.nan_to_num(sb[s])[:, None] * rng.standard_normal((len(ids), N_CRPS_DRAWS))
        g_draws = gbm_stats[s].to_numpy()[:, None] + s_epi[s] * noise + alea
        t2_epi = split_normal_draws(sc["q10"][s].to_numpy(), sc["q50"][s].to_numpy(),
                                    sc["q90"][s].to_numpy(), N_CRPS_DRAWS, rng)
        t2_draws = t2_epi + alea
        t2_draws_store[s] = t2_draws
        rows.append({"target": target, "role": role, "model": tag, "stat": s, "kind": "dist",
                     **dist_scores(g_draws, a, w), "s_epi": s_epi[s]})
        rows.append({"target": target, "role": role, "model": "tier2_sidecar", "stat": s,
                     "kind": "dist", **dist_scores(t2_draws, a, w)})
    ctx = dict(ids=ids, w=w, actual=actual, marcel=marcel_stats, gbm=gbm_stats,
               tier2=sc, t2_draws=t2_draws_store, target=target, role=role)
    return rows, ctx


# ---------------------------------------------------------------- hybrid

def hybrid_rows(b: BT.Bundle, role: str, ctxs: dict, rng):
    """Residual GBM on tier2 stat residuals, expanding over dev targets; scores 2022-24."""
    rows = []
    for target in (2022, 2023, 2024):
        train = BT.train_slice(b, target)
        prior = [t for t in (2021, 2022, 2023) if t < target]
        Xs, ys, ws = [], [], []
        for tp in prior:
            c = ctxs[(tp, role)]
            f = feature_frame(BT.train_slice(b, tp), role, "k", [tp],
                              {tp: c["ids"]}).set_index("mlbam_id").reindex(c["ids"])
            for s in BT.STATS[role]:
                f[f"t2_{s}"] = c["tier2"]["pred_mean"][s].to_numpy()
            f["t2_width"] = (c["tier2"]["q90"][BT.KEY_STAT[role]]
                             - c["tier2"]["q10"][BT.KEY_STAT[role]]).to_numpy()
            f["marcel_key"] = c["marcel"][BT.KEY_STAT[role]].to_numpy()
            f["gap"] = f[f"t2_{BT.KEY_STAT[role]}"] - f["marcel_key"]
            Xs.append(f.drop(columns=["season"]))
            ys.append(pd.DataFrame(
                {s: c["actual"][s].to_numpy() - c["tier2"]["pred_mean"][s].to_numpy()
                 for s in BT.STATS[role]}, index=c["ids"]))
            ws.append(pd.Series(c["w"], index=c["ids"]))
        X = pd.concat(Xs)
        Y = pd.concat(ys)
        W = pd.concat(ws)
        c = ctxs[(target, role)]
        ft = feature_frame(train, role, "k", [target],
                           {target: c["ids"]}).set_index("mlbam_id").reindex(c["ids"])
        for s in BT.STATS[role]:
            ft[f"t2_{s}"] = c["tier2"]["pred_mean"][s].to_numpy()
        ft["t2_width"] = (c["tier2"]["q90"][BT.KEY_STAT[role]]
                          - c["tier2"]["q10"][BT.KEY_STAT[role]]).to_numpy()
        ft["marcel_key"] = c["marcel"][BT.KEY_STAT[role]].to_numpy()
        ft["gap"] = ft[f"t2_{BT.KEY_STAT[role]}"] - ft["marcel_key"]
        ft = ft.drop(columns=["season"])
        for s in BT.STATS[role]:
            ok = np.isfinite(Y[s].to_numpy()) & np.isfinite(W.to_numpy()) & (W.to_numpy() > 0)
            m = HistGradientBoostingRegressor(**HP_HYBRID)
            m.fit(X[ok], Y[s][ok], sample_weight=W[ok])
            corr = m.predict(ft)
            pred = c["tier2"]["pred_mean"][s].to_numpy() + corr
            a = c["actual"][s].to_numpy()
            rows.append({"target": target, "role": role, "model": "hybrid", "stat": s,
                         **BT.weighted_metrics(pred, a, c["w"])})
            d = c["t2_draws"][s] + corr[:, None]
            rows.append({"target": target, "role": role, "model": "hybrid", "stat": s,
                         "kind": "dist", **dist_scores(d, a, c["w"])})
    return rows


# ---------------------------------------------------------------- entry

def main(hp=HP_A, tag="gbm", hybrid=True, out="data/artifacts/m4/m4_results.json"):
    b = BT.load_bundle()
    sidecar = pd.read_parquet(Path(C.ARTIFACTS) / "backtest_predictions.parquet")
    sidecar = sidecar[sidecar.tier == "tier2"]
    rng = np.random.default_rng(7)
    rows, ctxs = [], {}
    for target in C.DEV_TARGETS:
        for role in BT.ROLES:
            r, ctx = eval_target(b, role, target, sidecar, rng, hp=hp, tag=tag)
            rows += r
            ctxs[(target, role)] = ctx
            print(f"done {role} {target}")
    if hybrid:
        for role in BT.ROLES:
            rows += hybrid_rows(b, role, ctxs, rng)
            print(f"hybrid done {role}")
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(p.read_text()) if p.exists() else []
    p.write_text(json.dumps(existing + rows, default=BT._json_safe))
    print(f"wrote {len(rows)} rows -> {p}")
    return rows


if __name__ == "__main__":
    import sys
    if "--sensitivity" in sys.argv:
        main(hp=HP_B, tag="gbm_B", hybrid=False)
    else:
        main()
