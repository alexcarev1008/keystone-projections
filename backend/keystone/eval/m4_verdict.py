"""Aggregate m4_results.json into the pre-registered A1/A2/A3 verdicts + tables."""
import json
import sys

import pandas as pd

KEY = {"H": "woba", "P": "fip"}


def main(path="../data/artifacts/m4/m4_results.json"):
    df = pd.DataFrame(json.loads(open(path).read()))
    point = df[df.kind.isna()] if "kind" in df else df
    dist = df[df.kind == "dist"] if "kind" in df else pd.DataFrame()

    pt = point.pivot_table(index=["role", "stat", "target"], columns="model", values="rmse")
    print("== point RMSE (PA'-weighted), per target ==")
    print(pt.round(4).to_string())
    print("\n== point RMSE, 4-target mean ==")
    mean4 = point[point.target.isin([2021, 2022, 2023, 2024])].pivot_table(
        index=["role", "stat"], columns="model", values="rmse")
    print(mean4.round(4).to_string())

    if not dist.empty:
        for v in ("crps", "cov80", "pinball"):
            print(f"\n== {v}, per target ==")
            print(dist.pivot_table(index=["role", "stat", "target"], columns="model",
                                   values=v).round(4).to_string())

    print("\n== pre-registered verdicts ==")
    for role in ("H", "P"):
        k = KEY[role]
        sub = point[(point.role == role) & (point.stat == k)]
        p = sub.pivot_table(index="target", columns="model", values="rmse")
        if "gbm" in p:
            wins = int((p.gbm <= p.tier2_sidecar).sum())
            mean_ok = (p.gbm.mean() < p.tier2_sidecar.mean()) and (p.gbm.mean() < p.marcel.mean())
            print(f"A1 {role}/{k}: gbm beats tier2 in {wins}/4; mean gbm {p.gbm.mean():.4f} "
                  f"tier2 {p.tier2_sidecar.mean():.4f} marcel {p.marcel.mean():.4f} "
                  f"-> {'PASS' if wins >= 3 and mean_ok else 'FAIL'}")
        if not dist.empty:
            ds = dist[(dist.role == role) & (dist.stat == k)]
            dp = ds.pivot_table(index="target", columns="model", values="crps")
            cv = ds.pivot_table(index="target", columns="model", values="cov80")
            if "gbm" in dp:
                wins = int((dp.gbm < dp.tier2_sidecar).sum())
                c = cv.gbm.mean()
                print(f"A2 {role}/{k}: gbm CRPS beats tier2 in {wins}/4; gbm cov80 {c:.3f} "
                      f"(tier2 recon {cv.tier2_sidecar.mean():.3f}) "
                      f"-> {'PASS' if wins >= 3 and .75 <= c <= .85 else 'FAIL'}")
            if "hybrid" in p:
                sub3 = p[p.index >= 2022]
                wins = int((sub3.hybrid <= sub3.tier2_sidecar).sum())
                mean_ok = (sub3.hybrid.mean() < sub3.tier2_sidecar.mean()
                           and sub3.hybrid.mean() < sub3.gbm.mean())
                hcrps = dp[dp.index >= 2022]
                crps_ok = hcrps.hybrid.mean() <= hcrps.tier2_sidecar.mean() if "hybrid" in hcrps else None
                hcov = cv[cv.index >= 2022].hybrid.mean() if "hybrid" in cv else None
                cov_ok = hcov is not None and .75 <= hcov <= .85
                print(f"A3 {role}/{k}: hybrid beats tier2 in {wins}/3 (2022-24); "
                      f"means hybrid {sub3.hybrid.mean():.4f} tier2 {sub3.tier2_sidecar.mean():.4f} "
                      f"gbm {sub3.gbm.mean():.4f}; CRPS ok {crps_ok}; cov80 {hcov:.3f} "
                      f"-> {'PASS' if wins >= 2 and mean_ok and crps_ok and cov_ok else 'FAIL'}")


if __name__ == "__main__":
    main(*sys.argv[1:])
