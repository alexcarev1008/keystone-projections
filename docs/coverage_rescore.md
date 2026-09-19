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

<!-- filled in below after the compute; nothing above this line changed after. -->
