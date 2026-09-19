# Coverage re-score under Marcel anchoring — pre-registration

Fable, 2026-09-18. Written and committed BEFORE any coverage number was computed. The result
below the "---" is measured on frozen artifacts and reported verbatim.

## Motivation

The memo, README and Methodology all quote 80% interval coverage of ~.83 (hitters) / ~.75
(pitchers), landing in [.75, .85] on 9 of 10 stat rows for the 2025 holdout, and in-band for
the key stat on the dev targets (H .819 / P .761 mean). Those numbers were measured on
intervals centred on the Tier 2 posterior (`interval_coverage` in
`backend/keystone/eval/backtest.py`, `simulate_season` at each player's actual PA/IP). Production
does not ship those intervals: `project._anchor_to_marcel` shifts each stage's h=1 draws in
logit space so the median lands on Marcel's stage rate; wOBA/FIP quantiles are then derived
from the anchored stage draws. Waterfall-vs-headline gap on H/wOBA is mean −.018, max .088 —
roughly half the typical q50→q10 distance
(`docs/interview_prep.md` §B, `data/artifacts/waterfall.parquet` vs `projections.parquet`).

An interval that moves relative to the outcome it is meant to cover does not carry its
coverage with it. This re-score checks whether the shipped-artifact coverage claim survives.

## Estimand

**Primary.** Empirical coverage of the AS-SHIPPED 80% intervals against realized outcomes, per
(role, stat), by target. The as-shipped interval for a (player, target, stat) is:

    shipped_q10 = marcel_stat + (tier2_q10 − tier2_q50)
    shipped_q50 = marcel_stat
    shipped_q90 = marcel_stat + (tier2_q90 − tier2_q50)

where `marcel_stat` is the Marcel-derived stat for that player at that target (from
`MARCEL.marcel` + `derive_hitter/pitcher`, computed on the leakage-safe `train_slice` at each
target) and `tier2_*` are the Tier 2 quantiles from
`data/artifacts/backtest_predictions.parquet` (the committed sidecar). "Actual" is the
observed rate from the target season's counts, derived through the same
`stats_from_stage_probs` path the backtest uses.

**This is an approximation, and its scope is stated up front.** `_anchor_to_marcel` operates
per-stage on stage-probability draws; derived stats are nonlinear combinations of those. The
sidecar carries only derived-stat quantiles, not stage-level draws, so I cannot reconstruct
the anchored intervals exactly without refitting — and the task prohibits refitting. The
approximation preserves the two properties `_anchor_to_marcel` actually enforces: (i) the
posterior *median* of the derived stat lands on Marcel's derived stat (exact in the
linearised limit; wOBA/FIP are close to linear in stage rates around fitted values), and
(ii) the posterior *width* around that median is Tier 2's width. It ignores the mild
non-linearity that reshapes the tail of a nonlinear combination under a per-stage shift.
The alternative — refitting to recover per-stage draws — was explicitly excluded by the task.

**Secondary (isolates the anchor effect).** Coverage of the UNANCHORED Tier 2 intervals on
the same population and same "actual" using sidecar q10/q50/q90 directly. The difference
between primary and secondary is the anchor effect.

**Additional caveat, reported not gating.** Both intervals above are posterior-on-rate bands
(no binomial noise added; the sidecar didn't record it). The .83/.75 numbers the memo
quotes come from `interval_coverage`, which adds binomial noise at each player's actual
PA/IP via `simulate_season`. Both effects push the primary number down — anchoring is what
this re-score is about; the posterior-vs-predictive gap is orthogonal and is noted, not
studied here.

**Population.** The eval intersection each target already uses (`eval_population` in
`backtest.py`, PA'/BF' ≥ 200 in T with prior history). Same rows as the .83/.75 measurement,
minus any player without a Marcel line at that target (Marcel needs T−1..T−3 history).

**Weighting.** Primary: PA'/BF'-weighted mean coverage (matches the backtest's convention).
Secondary: unweighted, so a small number of high-PA players cannot dominate.

**Anchor-shift distribution (mechanism).** For each (player, target, role, stat), compute
`s = (marcel_stat − tier2_q50) / (tier2_q90 − tier2_q10)` — the anchor shift as a fraction
of the nominal interval width. Report the 10th, 25th, 50th, 75th, 90th and 99th percentiles
by role×stat. A small mean with a long tail is a different problem than a uniform one.

## Acceptance band and decision rule

Fixed now, before any number is computed:

- Nominal 80% interval → in-band = cov80 ∈ [.75, .85]. Same band the project has always
  used, same window as the pre-registered gate (MANUAL §6, `backtest.py` `GATE_COV_RANGE`).
- 10 rows = 5 stats × 2 roles for dev; the same 10 for 2025.

**Shipped-claim stands if BOTH:**
1. Dev-target primary coverage (PA-weighted mean across 2021–2024) for the key stat is in
   [.75, .85] for BOTH roles.
2. On 2025, ≥ 8 of the 10 (role, stat) primary rows fall in [.75, .85].

**Fails if either condition breaks.** No graded middle ground; no tolerance widening after
seeing the number. The primary decides. The secondary/unweighted/percentile tables are
diagnostic; they do not change the verdict.

## Compute plan

- Reuse the committed `backtest_predictions.parquet` for Tier 2 q10/q50/q90 (no refitting).
- Compute Marcel-derived stats via the existing `MARCEL.marcel` on
  `train_slice(b, target).ps[role]` and the existing `stats_from_stage_probs` (same code path
  the backtest uses for `marcel` rows, so this reproduces the memo's Marcel RMSE by
  construction — verified numerically before reporting anything else).
- Compute actuals via `actual_stage_probs` + `stats_from_stage_probs` at each target's actual
  PA/IP (same code path).
- Write it as `backend/keystone/eval/coverage_rescore.py` (small, imports the existing
  backtest utilities), with a unit test.

## Ordering

Dev 2021–2024 first — always development data, no holdout question. The dev table is
committed before any 2025 number is loaded. Then 2025, with a "this is the third time 2025
has been touched" note so a reader can judge for themselves.

## Commitment

**This result will be reported whatever it says.** No model, interval or config is changed in
response to it. If any part of the shipping claim fails its pre-registered acceptance rule,
`docs/research_memo.md`, `README.md` and `frontend/src/pages/Methodology.tsx` are corrected —
not softened, not hedged past what the numbers support, and not accompanied by a retune.

This is a descriptive measurement of a frozen artifact.

Anything the compute surfaces that asks for a modelling decision is written down as a
question in `STATUS.md`; nothing is executed on it in this task.

---

## Results

Compute run 2026-09-18 against the committed sidecar
(`data/artifacts/backtest_predictions.parquet`, targets 2021–2025, tier=tier2). No refits.
The `keystone.eval.coverage_rescore` module and its test carry the code. Numbers below are the
verbatim output of that module; nothing above this line changed after the compute ran.

### Dev targets 2021–2024 — PA/IP-weighted mean cov80

| role/stat | anchored (shipped-approx) | unanchored (Tier 2 sidecar) | width q90−q10 |
|---|---:|---:|---:|
| H k_pct  | .713 | .732 | .0820 |
| H bb_pct | .659 | .663 | .0389 |
| H hr_pct | .596 | .640 | .0228 |
| H babip  | .495 | .522 | .0438 |
| H **wOBA** | **.629** | **.657** | .0612 |
| P k_pct  | .751 | .782 | .0939 |
| P bb_pct | .599 | .615 | .0390 |
| P hr_pct | .533 | .545 | .0159 |
| P babip  | .428 | .444 | .0354 |
| P **FIP**  | **.584** | **.551** | 1.253 |

**In-band ([.75, .85]) on dev, anchored, PA-weighted: 1 of 10 rows (P k_pct .751).**
Unanchored: 2 of 10 (P k_pct .782, plus itself is the only near-band). Both key stats miss
by ~.10–.20 in either direction. FIP is the only row where anchoring *helps* the level
(Marcel is less biased than Tier 2 on P/FIP, so re-centring on Marcel raises coverage).
Every other row is worse or unchanged under anchoring.

### 2025 holdout (this is the third time 2025 has been touched — invalid run, valid re-run, this re-score)

| role/stat | anchored | unanchored | width | posterior-predictive from backtest.json (memo) |
|---|---:|---:|---:|---:|
| H k_pct  | .683 | .687 | .0777 | .765 |
| H bb_pct | .626 | .643 | .0366 | .821 |
| H hr_pct | .576 | .602 | .0194 | .806 |
| H babip  | .490 | .525 | .0415 | .806 |
| H **wOBA** | **.640** | **.652** | .0542 | **.831** |
| P k_pct  | .683 | .756 | .0846 | .828 |
| P bb_pct | .727 | .725 | .0390 | .840 |
| P hr_pct | .453 | .469 | .0132 | .812 |
| P babip  | .412 | .397 | .0351 | .785 |
| P **FIP**  | **.543** | **.505** | 1.066 | **.748** |

**In-band on 2025, anchored, PA-weighted: 0 of 10.** Unanchored: 1 of 10 (P k_pct .756).
The rightmost column reproduces the memo's cited numbers (`backtest.json` tier2 rows,
`interval_coverage` posterior-predictive), and it lands in-band for 9 of 10 as the memo says —
against a **different interval object** than what production ships.

### Acceptance verdict

Pre-registered rule (above): shipped-claim stands only if BOTH
(i) dev-target key-stat PA-weighted mean cov80 in [.75, .85] for both roles AND
(ii) ≥ 8 of 10 (role, stat) rows in-band on 2025.

    dev_key_H = 0.6289  →  in-band? False
    dev_key_P = 0.5839  →  in-band? False
    holdout_in_band = 0 / 10  →  ≥ 8? False
    shipped_claim_stands = False

**Both legs fail. Verdict: (c) coverage breaks.**

### The mechanism, isolated

Two separate effects push the shipped-artifact coverage below what the memo cites, and they
are not the same effect. The re-score cleanly identifies which does the damage.

1. **Bandwidth mismatch (dominant).** The .83/.75 figure comes from `interval_coverage` in
   `backend/keystone/eval/backtest.py`, which builds posterior-*predictive* intervals by
   `simulate_season` — binomial sampling on top of each stage's posterior draws at the
   player's actual PA/IP. The bands in `projections.parquet` (what the frontend renders on a
   player page) come from `_quantile_frame` on the *derived-stat draws*, with no binomial
   noise added. For a 500-PA regular the binomial contribution to wOBA sd is on the order
   of .022 — comparable to the width of the shipped bands themselves (.06 q10→q90), so
   removing it takes coverage from ~.83 down to ~.65 before anchoring even enters. Every
   row above where the "posterior-predictive from backtest.json" column reads .78–.83 and
   the "unanchored" column reads .40–.65 is the same effect: two different interval objects.
2. **Marcel anchoring (secondary, per-stat direction).** On top of (1), anchoring changes
   the level of the shipped bands by re-centring on Marcel. The AGGREGATE effect on cov80
   is a few points either way — for H/wOBA and H/hr_pct and P/k_pct anchoring *drops*
   coverage (Tier 2 median is closer to realized than Marcel is); for P/FIP anchoring
   *raises* coverage (Marcel is less biased than Tier 2 on FIP). The per-player anchor
   shift is not small, though — see the next table.

### Anchor shift distribution (`s = (marcel_stat − tier2_q50) / (tier2_q90 − tier2_q10)`)

Per-player shift as a fraction of the nominal interval width, pooled over dev targets:

| role/stat | n | \|s\| p10 | p25 | p50 | p75 | p90 | p99 | signed median | signed mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H babip   | 1350 | .04 | .10 | .20 | .32 | .45 | .70 | +.19 | +.19 |
| H bb_pct  | 1350 | .02 | .05 | .11 | .20 | .30 | .57 | +.07 | +.08 |
| H hr_pct  | 1350 | .02 | .06 | .13 | .25 | .38 | .71 | +.12 | +.14 |
| H k_pct   | 1350 | .02 | .06 | .13 | .23 | .35 | .67 | −.03 | −.02 |
| H **wOBA** | 1350 | .04 | .09 | .19 | .32 | .44 | .70 | +.18 | +.20 |
| P babip   | 1320 | .04 | .11 | .22 | .38 | .57 | .91 | −.03 | −.03 |
| P bb_pct  | 1320 | .03 | .06 | .13 | .24 | .36 | .64 | −.03 | −.02 |
| P hr_pct  | 1320 | .03 | .06 | .13 | .22 | .31 | .57 | −.01 | −.01 |
| P k_pct   | 1320 | .03 | .06 | .13 | .24 | .37 | .69 | +.07 | +.07 |
| P **FIP**  | 1320 | .03 | .07 | .15 | .26 | .38 | .63 | −.08 | −.07 |

Read across a row: on H/wOBA the median player's shipped-band centre moves ~19% of the
interval width away from Tier 2's, one player in four sees a shift ≥ 32%, and one in a hundred
sees ≥ 70% — the anchor is a light-tailed shift for most players and a very substantial one
for a nontrivial minority. The signed columns show DIRECTION: for hitters Marcel projects
generally *above* Tier 2 (positive signed shift on wOBA, BABIP, HR%, BB%; negative on K%);
for pitchers Marcel is *below* Tier 2 on FIP (negative signed shift; Marcel is less biased
here). This mirrors the RMSE story where Tier 2 out-shrinks Marcel on the noisier stages.

The `-.018 mean wOBA gap` finding in `docs/interview_prep.md` §B was computed on the current
production artifacts (2026-window fits, 2027 target, projections.parquet vs waterfall.parquet)
and is a shipped-q50 minus Tier 2 median (not divided by width), so the sign appears reversed
here (my `s` is Marcel minus Tier 2 median). Both agree that the anchor is a substantial
per-player shift; the aggregate sign is measurement-dependent.

### Approximation quality check

My approximation preserves each player's Tier 2 interval WIDTH and shifts the centre onto
Marcel. Real production applies the anchor per-stage; derived-stat widths under that anchor
are close to Tier 2's but not exactly equal (small nonlinearity). Sanity check: mean interval
widths in `projections.parquet` (shipped 2027 h=1) are 5–17% larger than in the sidecar 2024
across the 10 role×stat combinations — different fit windows, different populations, but
same order of magnitude. If production widths are systematically larger than my
approximation, the true shipped cov80 is slightly higher than reported here — but not by
enough to move it into [.75, .85] on any row that is currently below .70.

## Corrections applied (verdict (c))

Per the pre-registered commitment, the memo/README/Methodology have been corrected in
lockstep with this file. The claim as it stood — "80% intervals covered 83%/.75 on 2025" —
described `interval_coverage`'s posterior-predictive bands (which do land there), not the
bands `projections.parquet` writes and the frontend displays (which cover .40–.75). The
model has not been retuned. See:

- `docs/research_memo.md` §"The short version" and §5.
- `README.md` — Results table caption and Limitations.
- `frontend/src/pages/Methodology.tsx` — "Model iteration (M2)" paragraph and the 2025
  holdout caption.

## Questions for later (written to STATUS.md, not executed on)

- The natural fix — ship posterior-predictive intervals by adding `simulate_season` at
  projected PA — is a modelling/pipeline decision, not a description. Handed to STATUS,
  not made here.
- Whether the intended user semantics of an "80% band" on a projection is "80% of realized
  seasons" (predictive, wider) or "80% of the true-talent posterior" (rate, narrower) is
  also a product decision, not a re-score.
