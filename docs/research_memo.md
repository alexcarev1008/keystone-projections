# KEYSTONE — research memo

Daniel Cho · September 2026 · projections for 2027, data through the 2026 season to date

## The short version

KEYSTONE is a Bayesian, component-level projection system for MLB hitters and pitchers. It was
built to beat Marcel and was scored against Marcel under rules written down before each run.
It didn't clear the bar. Across the four development seasons (2021–2024) the locked Bayesian model
beat Marcel on hitter wOBA in 2 of 4 years and on pitcher FIP in 1 of 4. The shipping gate needed
3 of 4. On the one-time 2025 holdout it lost both key stats narrowly (wOBA .0309 vs .0305, FIP
.7399 vs .7317), even though it won 5 of the 8 component rows underneath them. So the system
ships **Marcel's point projections with the Bayesian model's uncertainty bands**. Those bands are
the part that did validate: 80% intervals covered 83% of hitters and 75% of pitchers on 2025, and
landed in the [.75, .85] band on 9 of 10 stat rows.

Every change in this memo was run as a pre-registered experiment. Each one had a hypothesis, an
expected result and an accept/reject rule, and all of that was committed to `docs/fable/` before
the run it judges. Two experiments that improved the headline number were rejected because they
failed their own sub-checks (E2, E3). A gradient-boosting challenger that beat the Bayesian FIP
points was not shipped because it didn't beat Marcel (M4). When a scheduling race meant the holdout
ran with the wrong configuration, the result was ruled invalid, and the rules for the one re-run
were written down before the re-run happened. The rest of this memo explains what the model does,
why it's built this way, what the evidence shows, and what I still don't trust.

Every number below is quoted from a committed file, named in brackets. None was re-derived for this memo.

---

## 1. What the model does

**Component stages, not rates.** Each plate appearance is modelled as a chain of conditional
binomials. For hitters that's strikeout, then unintentional walk, then HBP, then HR per contact PA,
then hit on a ball in play (BABIP), then extra-base hit per non-HR hit, then triple per XBH.
Pitchers get the first five. wOBA and FIP aren't modelled at all. They are *derived* from the
stage probabilities with one verified formula, and that same formula is used for actuals,
projections and simulations, so every tier is scored through the same code path
[`M1_audit.md`, "Checks that came back clean"].

**Tier 2: one state-space model per (role, stage)** [`CONTEXT.md` §2]:

```
theta[i, first] = lam * z(log PA'_first) + sigma_pop * e
theta[i, t]     = theta[i, t-1] + g[age[i, t]] + tau * e          (talent random walk + aging)
y[i, t]         ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t] + X_park . phi + sigma_obs * eps))
```

It is non-centred and sampled with nutpie. The `sigma_obs` term (transient season noise) and a
common league-environment shock at projection time are the two changes the research phase
accepted (§3). Park effects apply to the batted-ball stages. The log-PA term in the first-season
prior shrinks part-timers toward a lower mean rather than toward league average.

**Why component chains and not a regression on wOBA or FIP.** Three reasons, and each can be
checked against the fitted parameters:

1. *Reliability is learned per stat.* Each stage has its own binomial denominator and its own
   population spread, so the model regresses K% a little and BABIP a lot without anyone
   hard-coding stabilization points. Fitted sigma_pop is .359 for H/k against .091 for H/hit_bip
   [`CONTEXT.md` §6].
2. *DIPS comes out of the fit.* Nobody told the model that pitchers control little of their BABIP.
   It learned a talent spread on hit_bip of .047 for pitchers against .091 for hitters, about half
   [`CONTEXT.md` §5].
3. *The errors can be diagnosed.* A rate-level regression that loses to Marcel tells you only that
   it lost. The component model tells you *where*: hitter HR% because of park scoring (M1), BB%
   because the walk chased T−1 (M2), relievers, the 2022 dead-ball environment. Every research
   decision below starts from a component-level diagnosis like these.

**Playing time is a separate model.** A Bayesian hurdle, P(plays) × E[PT | plays], replaced
Marcel's `.5·PA₁ + .1·PA₂ + 200` rule (§3, M3). The multi-year outlook is *expected* production,
meaning the chance of playing times the conditional line, reported per horizon as `p_play`,
`pt_expected` and `p_regular` [`M3_playing_time.md` §4].

**Stack:** PyMC 5 + nutpie for fitting, parquet/JSON artifacts, a read-only FastAPI service that
never fits anything, and React + Recharts for the front end.

## 2. How it was judged

- **Rolling-origin backtests** on targets 2021–2024. A projection for season T sees only seasons
  ≤ T−1. `train_slice` enforces this before any table is built, and end-to-end perturbation tests
  check it (`tests/test_backtest_leakage.py`; the M4 challenger now has its own,
  `tests/test_m4_leakage.py`).
- **The gate** [`CONTEXT.md` §3; MANUAL §6]: Tier 2 ships only if its key-stat RMSE (wOBA for
  hitters, FIP for pitchers, PA′-weighted) is ≤ Marcel's in at least 3 of 4 dev targets **and**
  its mean 80% interval coverage is in [.75, .85].
- **One holdout, 2025.** It is scored once, after the configuration is locked.
- **Marcel is a real baseline, not a strawman.** It is a faithful Tango implementation (5/4/3 and
  3/2/1 weights, 1,200-PA regression, June-30 age adjustment), and the audit confirmed it
  [`M1_audit.md`].

## 3. What the backtests showed

### Development seasons, locked configuration [`data/artifacts/backtest.json`]

| key stat | 2021 | 2022 | 2023 | 2024 | wins | cov80 (mean) |
|---|---|---|---|---|---|---|
| H wOBA — Marcel | .0336 | .0358 | .0304 | .0337 | | — |
| H wOBA — Tier 2 | .0338 | **.0326** | .0321 | **.0326** | 2/4 | .819 ✓ |
| P FIP — Marcel | .7831 | .8214 | .8389 | .7356 | | — |
| P FIP — Tier 2 | .7987 | .8907 | **.8190** | .7572 | 1/4 | .761 ✓ |

Both gates fail. On hitters the model beats Marcel on the four-year mean (.0328 vs .0334), and
M2c argued that the mean is the better measure of skill: counting years is a sign test with
n = 4 and it ignores margins. The gate was left as written anyway, because it had been
pre-registered and changing it after seeing the numbers is exactly what pre-registration exists to
prevent [`M2_experiments.md`, "The mean and the gate disagree on hitters"]. The recommended fix
for *future* gates is a paired, by-player block bootstrap on the mean difference.

### The 2025 holdout [`M2_experiments.md`, "Attempt 2"]

| 2025 | Marcel | Tier 2 | Tier 2 cov80 |
|---|---|---|---|
| **H wOBA** | **.0305** | .0309 | .83 |
| H k / bb / hr / babip | .0364 / .0197 / .0117 / .0327 | .0374 / **.0195** / .0118 / **.0302** | .76 / .82 / .81 / .81 |
| **P FIP** | **.7317** | .7399 | .75 |
| P k / bb / hr / babip | .0380 / .0172 / .0100 / .0336 | **.0375** / .0182 / **.0098** / **.0319** | .83 / .84 / .81 / .78 |

**The aggregate comparison lost on both key stats while most components won.** Tier 2 won BABIP
for both roles, pitcher HR% and K%, and hitter BB%, which is 5 of 8 component rows. It lost hitter
K%, pitcher BB% and, by .0001, hitter HR%. This happens because wOBA and FIP don't weight the
components equally. FIP puts 13× on HR and 3× on BB, so pitcher BB% (the one pitcher component the
model reliably loses) carries a lot of weight. Hitter wOBA is dominated by HR (wHR ≈ 2.05) and K%.
Marcel also had its best year of the five scored in 2025 (both key-stat RMSEs below every dev-year
value). One year decides nothing about the hitter mean-vs-gate argument in either direction.

Against the expectation recorded before any 2025 number existed ("H close to or better, P worse,
coverage in band"): hitters came out close but not better, pitchers worse, coverage in band. That's
two of three.

**What production ships as a result:** Marcel point projections, with Tier 2 bands, aging drift and
waterfall around them. The Methodology page says this in plain terms. The bands are
holdout-validated at h = 1. The points are the baseline because the model didn't earn them.

## 4. What each research mission changed

The research phase ran as four missions, each with its own pre-registrations. In order:

**M1 — statistical red team** [`M1_audit.md`]. *Found and fixed one bug that drove the headline
result.* Tier 2 removes park effects from talent, and the backtest then scored those park-neutral
projections against actuals recorded in each player's real park. Marcel never models parks, so it
keeps them implicitly and only Tier 2 was penalized. The audit predicted the size of the error from
park_sd before running anything (≈ .008 in HR rate). The fix (score in the player's T−1 park,
which is leakage-safe) moved hitter HR% RMSE .0155 → .0128 and hitter wOBA .0364 → .0333 on the
full re-run [`STATUS.md`, M1 results]. The audit also *refuted* a hypothesis I had favoured: that
part-timers in the fit population were over-shrinking talent. Fitted talent spread matched the
observed spread among regulars to within ~6%. Leakage, stage math, age convention, traded players,
two-way players and 2020 all came back clean.

**M2 — model experiments, a lock, and the holdout** [`M2_experiments.md`]. Six experiments, each
with a written accept rule:

- **E2, recency-weighted league environment: REJECTED.** FIP improved in 2 of 4 years; the rule
  needed 3. Taking it apart showed that the environment *shock* produced all of the calibration
  gain (FIP cov80 .732 → .755) and none of the damage, while the recency *point forecast* did all
  of the damage. The shock was kept on its own as E6.
- **E3, SP/RP role covariate: REJECTED.** The role effect was real (≈ 10 sd, correct signs) and
  overall FIP improved 3 of 4. But the reliever-subgroup check, which is the mechanism test, could
  not be verified because a sidecar file had been overwritten, and an unverifiable pass doesn't
  count as a pass. It also produced the worst fit in the project (r_hat 1.363).
- **E4, Student-t innovations: REJECTED**, and it produced the most useful finding of the round.
  Fitted tau fell by almost exactly √2, which is what you'd see if t(4) with variance 2τ² were
  just relabelling the same year-to-year variance. The variance was being conserved, not reduced,
  which meant the real problem was that the random walk forced *all* of it to be persistent.
- **E5, transient season noise: ACCEPTED** on every sub-check. Tau fell 21–53% on K and BB with
  sigma_obs ≥ 7 sd from zero. The T−1 chasing correlation crossed to Marcel's side on all four
  stages it was checked on (e.g. P/k +.116 → −.031). BB% improved in H 3/4 and P 4/4.
  Divergences fell 313 → 121, and the H/hit_bip funnel M1 had diagnosed mostly went away.
- **E6, environment shock only: ACCEPTED.** Fits were byte-identical to E5, and P FIP cov80 went
  .734 → .761. For the first time, both roles had coverage in band.
- **t4 for sampler geometry and correlated stages: DECLINED**, with the reasons written down.

The locked configuration is Tier 2 with `--obs-noise --env-mode shock`. **The holdout misfire:**
the first `make holdout` started one minute before the commit that wired the locked flags, so it
scored the *old* configuration. It was ruled invalid, and three pre-commitments were written before
the re-run: the locked config ships whatever 2025 says, no decision changes on the misfire numbers,
and there is one re-run only. The misfire's numbers are on record and nobody acted on them (they
were nearly identical anyway: H .0309 / P .7402). A code-level guard now refuses to run a holdout
whose flags don't match the dev run.

**M3 — playing time** [`M3_playing_time.md`]. *This is where the model beat the baseline clearly.*
Marcel PT has no zero mass and a 200-PA floor. On the 2025 population, 29% of projected hitters and
36% of projected pitchers had zero actual PT, and Marcel over-projected by +126 PA and +21.6 IP.
The pre-registered hurdle model beat Marcel **8 of 8** dev targets on RMSE (H −25%, P −11%). Bias
fell from +42..+127 PA to within ±7 PA, and from +6..+22 IP to within ±1.1 IP. *Follow-up:* the
hurdle initially had no talent term, so a star coming off a short season looked like a fading
veteran (Judge: 258 expected PA against Marcel's 410). A pre-registered talent covariate (a shrunk
wOBA or FIP-core deviation) beat the shipped hurdle 8 of 8 as well. Both coefficients were ≥ 4.8 sd
from zero, and Judge's h1 moved to p_play .96 and 545 expected PA [§7]. The follow-up also settled
whether hitter regulars were ~11% under Marcel. They were, and it was a real bias in the base
hurdle (−65 PA), which the talent term cut to −18. For pitcher regulars Marcel was the one that was
wrong (+27.5 IP) [§8].

**M4 — ML challenger** [`M4_ml_challenger.md`]. I red-teamed the Bayesian model with a
gradient-boosted challenger on an identical information set, plus a Bayesian+GBM hybrid. They were
compared on point RMSE and CRPS under accept rules committed before any challenger number existed
(commit `2f1db13`). **Hitters:** the hierarchical model beat both challengers on every score (GBM
wins 1 of 4 on points and 1 of 4 on CRPS; the hybrid adds nothing). The GBM was worst on hitter K%,
the highest-signal stage, which is exactly where per-player partial pooling should dominate.
**Pitchers:** the GBM beat Tier 2's FIP points 3 of 4 (.7938 vs .8131) and its CRPS 3 of 4, with
calibrated intervals (cov80 .827). The hybrid was the best point model on 2022–24 (.7770). Neither
ships. The GBM wins only 2 of 4 against Marcel, and its .0009 margin on the Marcel mean flips sign
under the pre-registered sensitivity config. The hybrid was the worst model on the board in 2023
and learned from ≤ 960 rows.

## 5. Honest open problems

1. **The h2–h4 bands are model-implied and have never been backtested.** The backtest scores
   h = 1 only. The small taus on hit_bip (.0105) and xbh (.0198) [`CONTEXT.md` §6] mean the model
   says those talents barely drift. If that's wrong, the multi-year bands are too narrow. The
   Methodology page labels them "model-implied, not backtested" [`M3_playing_time.md` §5]. A related point: hitter
   wOBA bands often *don't widen* from h1 to h4 (17.6% of hitters). That isn't a bug. Logit-space
   sd widens for 96–100% of players on every stage checked, and aging pulls HR/XBH rates down, which
   shrinks rate-space width faster than drift grows it [`STATUS.md`, artifact check A].
2. **Playing time is displayed for h1 only — a deliberate display decision.** The hurdle model is
   backtested at h1 only (`make pt-backtest`). At h2+ the simulation feeds its own simulated healthy
   seasons back in as the recent-PT feature, so expected PT rises with age for players whose recent
   PT was injury-depressed: Judge goes 545 / 579 / 620 / 646 PA from age 35 to 38 while his wOBA
   correctly declines .419 → .369 [`M3_playing_time.md` §7]. The model is unpatched; instead the
   player page shows h2–h4 as rates only ("rates only — playing time projected one year ahead"),
   because we do not display a number we have not validated. An h2+ PT backtest, or a fix to the
   feedback, is the precondition for showing it again.
3. **The production fit isn't fully converged.** Max r_hat is 1.16 (H/k) with 89 divergences
   across 12 fits, 69 of them in P/bb; P/hbp and H/triple are also above 1.1 [`CONTEXT.md` §5–6].
   The 2025 holdout fits reached r_hat 1.27 (P/hr) with 63 divergences [`M2_experiments.md`]. E5
   fixed the worst funnel, but low-tau stages still have the cumulative-sum geometry M1 described
   (F5). The next steps are marginalizing or reparameterizing the chain for those stages.
4. **Correlated pitcher stages are the most promising lead.** M2c declined to build a joint model:
   observed cross-stage residual correlations peak around .32 (P bb–k), and rebuilding would reset
   every validated result. M4 then gave the first quantitative evidence for it. The GBM's *only*
   information that Tier 2 lacks is other stages' lag-1 deviations, and it wins on exactly one
   thing, pitcher FIP. A pitcher's K, BB and HR rates come from one arsenal, not three independent
   walks. The pre-registered next test is to score the GBM and hybrid once on 2026 targets before
   wiring anything [`M4_ml_challenger.md` §7].
5. **Smaller items.** Rate and PT are treated as independent in expected production, which is wrong
   in detail because players who lose PT are usually declining, so counting stats lean optimistic
   for decliners. The league-environment point forecast is still a stale 3-year mean
   [`M1_audit.md` F3]. Relievers still pool with starters (E3 rejected). The reliever-covariate idea
   can be re-tested on top of the locked config.

## 6. What I'd do next

In order: (1) the pre-registered 2026-target score of the pitcher GBM and hybrid; (2) if that
holds, a joint pitcher model with a shared arsenal factor across K/BB/HR; (3) a block-bootstrap
gate on mean RMSE to replace year-counting, pre-registered before its first use; (4) a backtest of
h2–h4 calibration, scoring multi-year projections made from the earliest dev origins against
the seasons since; (5) MiLB translations and pitch-level Stuff+
indicators as Tier 3 inputs.

## Sources

| claim | file |
|---|---|
| model equations, fitted population parameters, sampler health | `docs/fable_context/CONTEXT.md` |
| dev per-year RMSE / coverage / gates | `data/artifacts/backtest.json` |
| park-scoring bug, audit checks | `docs/fable/M1_audit.md` |
| E2–E6, lock, holdout misfire + holdout | `docs/fable/M2_experiments.md` |
| playing-time hurdle, talent follow-up, regulars verdict | `docs/fable/M3_playing_time.md` |
| ML challenger, hybrid, verdict | `docs/fable/M4_ml_challenger.md` |
| band-widening analysis (artifact check A), post-M1 re-run | `STATUS.md` (Results) |
