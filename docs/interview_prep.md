# KEYSTONE — interview prep

Written by Fable, 2026-09-18, after a full inspection of the repo: every backend module, the
test suite, the frontend components, git history, and the artifacts themselves (meta.json,
backtest.json, the parquets via pandas — not the docs' summaries of them). Audience: Daniel,
defending this project to a Washington Nationals projection analyst who knows more baseball
statistics than he does. Every number is quoted from a named file; where I computed something
fresh during this inspection, I say so.

The one-sentence frame to hold onto: **this project's deliverable is not a model that beat
Marcel — it is a validated uncertainty layer, a playing-time model that did beat its baseline
8/8, and an unusually honest paper trail.** Everything below is in service of defending that
sentence under fire.

---

# Part I — The decision chain, in the order it happened

## 1. Component stages on a conditional binomial chain, not a regression on wOBA/FIP

**What was chosen.** Every PA' (PA − IBB − SH − CI, the wOBA denominator) is decomposed into a
chain of conditional binomials (`components.py`): K/PA', uBB/(PA'−K), HBP/(...), HR/contact,
(H−HR)/BIP (exactly BABIP), then XBH and 3B for hitters. wOBA and FIP are never modelled — they
are derived deterministically from the stage rates, through one function used identically for
actuals, projections and simulations (verified to machine precision vs FanGraphs formulas,
`STATUS.md` P2).

**The statistical reasoning.** A chain of conditional binomials is an exact factorization of the
multinomial over PA outcomes — no information is lost and simulated counts always sum back to PA.
The payoff is that each stage has its own trials denominator and its own fitted population spread
(sigma_pop), which together produce *per-stat reliability with no hard-coded stabilization
points*. On the logit scale, the data precision for a player-season is ≈ n·p(1−p) and the prior
(population) precision is 1/sigma_pop², so the model behaves as if each stat had a stabilization
sample of n* ≈ 1/(p(1−p)·sigma_pop²). Plug in the fitted values (`meta.json`):

- H K%: p≈.22, sigma_pop .359 → n* ≈ 45 PA. (Empirical split-half estimates put K% around 60 PA.)
- H BABIP: p≈.30, sigma_pop .091 → n* ≈ 580 BIP. (Empirical ≈ 800 BIP.)
- P BABIP: sigma_pop .047 → n* ≈ 2,200 BIP — more than a full season. That *is* DIPS, and nobody
  told the model: pitcher BABIP talent spread came out at half the hitters' (.047 vs .091).

So "K% shrinks little, BABIP shrinks a lot, pitcher BABIP shrinks almost entirely" is not a rule
we wrote — it is the fitted sigma_pop table, and it reproduces the received stabilization
ordering from first principles. That's the single best exhibit in the project.

**The alternative and its cost.** A direct regression on wOBA or FIP needs one error variance for
a quantity that mixes a 45-PA-stable skill and a 2,200-BIP-stable one; it can't shrink them
differently, it can't produce coherent count simulations, and when it loses you learn nothing.
The component model told us *where* it lost (hitter HR% → park scoring bug, M1; BB% → T−1
chasing, M2; relievers; the 2022 environment) — every research decision started from a
component-level diagnosis. Cost of the chain: stages are fit independently (see §A3).

## 2. Marcel as the baseline — and why beating it is genuinely hard

**What it is** (`models/marcel.py`, faithful Tango per the M1 audit): weighted 3-year event rates
(5/4/3 hitters, 3/2/1 pitchers) on the PA'/BF' basis, regressed toward the player's own
PA-weighted league mix with 1,200 PA' of ballast, one age multiplier (±.006/year under 29,
∓.003 over), PT = .5·PA₁ + .1·PA₂ + 200.

**What it's doing statistically.** Marcel is a hand-tuned approximation to the posterior mean of
a stationary talent model: weighted recency ≈ a Kalman filter's geometric decay, 1,200 PA of
league-average ballast ≈ the population prior, the age bump ≈ a linear aging curve. For a
league-average-ish population at h=1, that captures nearly all the recoverable signal. Look at
the dev table (`backtest.json`): naive extremes are last-season .0520 and league-average .0371
for H wOBA; Marcel gets .0334. The gap from "sensible shrinkage" to "perfect" is far smaller
than the gap from naive to sensible — everything after Marcel fights over a thin residual, most
of which is binomial noise and unforecastable league environment. Tier 2's fully-fit hierarchical
machinery moved the H wOBA mean from .0334 to .0328 (−1.8%). That is the honest size of the
prize at h=1.

**Cost of the alternative.** Using a weaker baseline (league average, last season, or a
"projections aggregate") would have manufactured a win. The project chose the baseline that
makes the null hypothesis hardest to reject — and then mostly failed to reject it, which is why
the writeup is credible.

## 3. The hierarchical state-space model, tau, and partial pooling

**What was chosen** (`models/state_space.py`): per (role, stage), a latent talent theta on the
logit scale that random-walks year to year — theta_t = theta_{t−1} + g[age] + tau·e — observed
through a binomial with the season's league logit as a fixed offset. Fit on a 6-season window
with nutpie, non-centred.

**What tau means.** tau is the standard deviation of *true talent's* year-over-year move, and it
is a learned recency weight: the filter's gain rises with tau. Fitted values (`meta.json`):
K% tau ≈ .10 (≈ 1.8 K% points of true drift per year — real skills move), BABIP tau ≈ .01
(≈ 0.2 points — BABIP talent is nearly static; year-to-year BABIP swings are noise, so the model
regresses them away). One mechanism, per-stat conclusions, all estimated.

**Partial pooling, concretely.** Posterior weight on a player's own season ≈ n·p(1−p) /
(n·p(1−p) + 1/sigma_pop²). For K% (sigma_pop .359): a 600-PA regular's season gets ~93% weight —
the model mostly believes him; a 90-PA callup gets ~66%. For BABIP (sigma_pop .091): the 600-BIP
regular gets ~51%; the callup ~13% — his .420 BABIP month is priced as luck. The same formula
spans both players and both stats; Marcel applies 1,200 PA of ballast to everyone equally.

**Cost.** ~12 MCMC fits per run, 20–40 minutes, real convergence blemishes (§B5), and a model
whose extra machinery must earn ~.0006 of wOBA RMSE to show up at all (see §D).

## 4. The first-season prior on log PA'

**What was chosen.** theta_first = lam·z(log PA'_first) + sigma_pop·e: a debut/window-entry
player's talent prior is centred not on league average but shifted by his (standardized log)
playing time.

**The problem it solves that league-average shrinkage does not: selection.** Playing time is not
random — it is the team's revealed belief about talent. A 90-PA September callup is not a draw
from the league-average talent distribution; he's a draw from the "org thought he was worth 90
PA" distribution, which is worse than average as a hitter population and better than replacement.
Shrinking him to league average overrates him; shrinking to a PA-informed mean prices the
selection in. The fitted loadings have exactly the right signs (`backtest_posteriors.parquet`,
computed during this prep): H/k lam = −.11 (high-PA debuts strike out less), H/hr +.12 (high-PA
debuts have more power), P/bb −.08 (high-BF debuts walk fewer). A second, quieter benefit: the
aging curve g is fit jointly on all seasons, and the PA prior absorbs part of the
selection-in/selection-out effect that poisons delta-method aging curves (players who vanish
after bad years). Remaining survivor bias is documented as a limitation, not solved.

## 5. Park effects as learned venue effects, batted-ball stages only

**What was chosen.** phi ~ N(0, park_sd) per venue, applied only to PARK_STAGES = {hr, hit_bip,
xbh, triple}, with exposure X = 0.5 × share of the player's PA' with each home team (half your
games are at home). No K/BB park terms. Projections can be run neutral or in the player's T−1
park; the backtest scores park-aware as of M1.

**Why batted-ball only.** The causal mechanism for a park effect is the flight of a batted ball —
fence distances, altitude, air. K and BB happen before the ball is in play; their park channels
(batter's eye, foul territory) are an order of magnitude weaker. Statistically the venue design
matrix is nearly collinear with team identity (exposure is home-team-based), so a K-stage phi
would mostly absorb *roster composition* — "Yankee Stadium raises K%" would really mean "the
Yankees employed high-K hitters." For batted-ball stages the physical mechanism is strong enough
to dominate that confound; for K/BB it isn't, and the coefficient would be a bias generator
dressed as a park factor. (Honesty check for §A: some roster confounding contaminates the
batted-ball phis too — see the H vs P park_sd asymmetry, .358 vs .122.)

**Why it mattered.** M1's one code-level root cause: the backtest scored park-*neutral* Tier 2
projections against in-park actuals, a handicap Marcel (park-implicit through raw rates) never
paid. The audit predicted the error size from park_sd before rerunning (≈.008 HR-rate sd;
√(.0124² + .008²) ≈ .0147 ≈ observed .0155) and the fix moved H HR% RMSE .0155 → .0128 and
H wOBA .0364 → .0333 (`M1_audit.md`, `STATUS.md`). Best example in the project of predicting a
fix's magnitude before running it.

## 6. sigma_obs — what it separates, and how it changed BB%

**What was chosen** (M2b/E5, accepted): a transient per-player-season logit noise term,
y ~ Binomial(n, invlogit(mu + theta + sigma_obs·eps)), drawn fresh each season and *never* added
to the walk.

**What it separates.** Three variance components in observed year-over-year movement: binomial
sampling noise (known from n), persistent talent drift (tau), and *transient extra-binomial
season effects* — health, umpire/schedule mix, one-year role quirks — that are real (the data
demand the variance; E4 proved it's conserved when you try to relabel it) but should not
propagate into next year's projection. Without the term, the random walk is the only home for
that variance, tau inflates, and the filter chases T−1 exactly on the stablest skills — M1-F4's
finding that tau ≈ .13 on BB%/K% implied absurd ~13%/year talent swings, and the chasing
correlation corr(T−1 deviation, error) was positive for Tier 2 while negative for Marcel.

**What changed** (`M2_experiments.md`, M2c): with obs_noise, tau fell H/bb .129 → .061 with
sigma_obs = .132 (≥ 7 sd from 0), the chasing correlation crossed to Marcel's side on all four
registered stages (P/k +.116 → −.031, H/bb +.048 → −.070), BB% RMSE improved in H 3/4 and P 4/4
targets, H wOBA mean .0333 → .0328, P FIP .8223 → .8162, and divergences fell 313 → 121 (the
H/hit_bip funnel mostly dissolved as a side effect). The E4 → E5 sequence is the best
*statistical reasoning* story in the project: a rejected experiment's failure mode (variance
conserved under t(4), fell by exactly √2) identified the correct fix (the variance needed a
non-persistent home, not a different tail shape).

## 7. The env shock at projection time

**What was chosen** (M2b/E6, accepted): mu_proj stays the boring 3-season-mean league logit, but
each posterior draw gets one persistent shock ~ N(0, sigma_env), where sigma_env is the sd of
year-over-year league logit changes (`league.projection_logit_recency`), shared across players
and horizons within a draw.

**What goes wrong without it.** Next season's league environment is itself a forecast (sigma_env
runs .015–.113 in logit depending on stage — HR is the wild one; `meta.json`). Omitting it makes
every player's interval too narrow *in a perfectly correlated way*: when the 2022 dead ball
arrives, everyone misses low together, and coverage collapses league-wide in exactly the year it
matters. P FIP cov80 went .734 → .761 with the shock; both roles entered the [.75,.85] band for
the first time. The E2 lesson attached to it: *forecasting the point* of the environment is hard
(the recency point forecast improved 2022 and damaged 2021/2023 — rejected 2/4), but *pricing
the variance* is nearly free and always right, because the shock is zero-mean. We kept the
variance, dropped the point.

## 8. The playing-time hurdle as a separate model, with a talent covariate

**Why separate.** Playing time is not a stage of the PA — it is the *number of trials*, with a
qualitatively different data-generating process: a point mass at zero (29% of Marcel's projected
hitter population and 36% of pitchers had zero actual PT in 2025) plus a right-skewed positive
part. A binomial stage can't represent "doesn't play"; Marcel's rule (.5·PA₁+.1·PA₂+200) has a
200-PA floor and no zero mass, and over-projected by +126 PA / +22 IP per player-season. Hurdle:
played ~ Bernoulli(invlogit(Xβ)), √PT/scale | played ~ Normal(Xγ, σ), E[PT] = p·scale²(μ²+σ²).
Result: beat Marcel PT 8/8 dev targets (H RMSE −25%, P −11%; bias +42..+127 PA → within ±7 PA;
`M3_playing_time.md` §3). This is the project's clean, unambiguous win.

**Why a talent covariate belonged in it.** Teams allocate PT on talent, so PT-history-only
features misread a star coming off a short season as a fading fringe player. The symptom was
Judge (285 PA in 2026): p_play .78, 258 expected PA. The bucket-level proof was better: hitter
*regulars* sat −65 PA biased under the base hurdle while Marcel was nearly unbiased there (+4);
the missing covariate was exactly the thing that distinguishes a resting star from a dying
career. A pre-registered shrunk wOBA/FIP-core deviation (ballast 600 PA / 180 IP) won 8/8 again,
cut the regulars bias to −18 PA, and moved Judge to p_play .96 / 545 PA (§7–§8). For pitcher
regulars the *hurdle* was right and Marcel was the biased one (+27.5 IP) — the model was never
tuned to match Marcel anywhere.

## 9. What the bands mean, and shipping bands from a model whose points didn't ship

**What a band is.** The shipped q10–q90 is a posterior-predictive interval for the player's
*realized season rate*: talent-posterior uncertainty + talent drift (tau·√h) + league-environment
shock (sigma_env) + transient season noise (sigma_obs) + binomial sampling at his actual (in
backtests) or projected PA. It answers "what range of season outcomes should I plan around,"
which is the roster-planning question, not "what is his true talent."

**Why coverage in [.75,.85] is the right check.** It's a pre-registered tolerance around the
nominal .80 sized to the sample: with n ≈ 330 players per role-target, the binomial se of an
honest 80% interval's empirical coverage is ≈ .022, so ±.05 is a ~2σ acceptance band —
tight enough to fail a wrong model (the pre-M2 pitcher fits *did* fail it at .73), loose enough
not to fail on noise. It was checked per-year, per-stat, and finally on the untouched 2025
holdout: H .83, P .75, and 9 of 10 stat rows in band (`M2_experiments.md`, Attempt 2).

**Why shipping them is defensible.** The gate separated two claims. The *points* claim ("my
central estimate beats Marcel's") failed its test, so Marcel's points ship. The *spread* claim
("my 80% intervals cover 80%") passed its dev test and then its one-shot holdout test — it is
the only part of the Bayesian model that was validated out-of-sample, and Marcel has no interval
machinery at all. The medians of the shipped draws are anchored to Marcel in logit space
(`project._anchor_to_marcel`), preserving Tier 2's spread and aging trajectory. The honest
asterisk — the anchored *composite* was never itself coverage-scored — is §A1, and you should
raise it before they do.

---

# Part II — The hard sections

## A. The strongest statistical arguments AGAINST our choices

Rehearse these in our own voice. The interviewer is looking for whether you know the soft spots.

**A1. The shipped object is a hybrid neither model was validated as.** Coverage was scored on
Tier 2's own predictive, centred on Tier 2's medians. Production re-centres those bands on
Marcel's points. The shift is not small: comparing waterfall step 5 (Tier 2's own park-aware h=1
value) with the shipped h=1 q50 across all 892 finite H/wOBA waterfalls (computed from
`waterfall.parquet` vs `projections.parquet` during this prep), the anchor moves the median by
−.018 wOBA on average, up to .088 — roughly *half the typical q50→q10 distance*. Coverage of a
band is not invariant to moving its centre. The defense: Marcel's points have equal-or-better
RMSE than the medians the bands were validated around, so re-centring on a better point should
not degrade coverage — but that is an argument, not a measurement. The measurement is cheap
(re-score cov80 with sidecar bands re-centred on Marcel points over the dev targets) and hasn't
been done. Say that: "computable, should have been, on the list."

**A2. The h2–h4 bands are pure model extrapolation.** The backtest scores h=1 only. Multi-year
width is driven by tau, and tau for hit_bip (.0105) and xbh (.0198) says those talents barely
move — if that's wrong, every multi-year band is too narrow. Worse for intuition: for most
hitters the *rate-space* band narrows h1→h4 (only 17.6% of H wOBA bands widen; `STATUS.md`
artifact check A), because aging drags the level down and a binomial band scales with p(1−p).
Logit-space sd does widen for 96–100% of players, so the model is internally coherent — but
"we're tighter on his age-38 wOBA than his age-35 wOBA" is a sentence you must be able to defend
as bounded-scale geometry, on a bounded stat, around a declining level, and never as "we know
more." The UI labels h2+ "model-implied, not backtested"; that label is the defense.

**A3. The independence-across-stages assumption is wrong twice, in opposite directions.** Stage
posteriors are combined index-by-index, so within a draw the talent components are independent —
which *understates* wOBA/FIP band width if component talents co-move. Meanwhile the env shock is
reseeded identically per stage (`project.py` seeds `default_rng(seed)` per stage and draws the
shock first — noted in STATUS), so environment shocks are *perfectly* correlated across stages —
which overstates their joint contribution. Both extremes are wrong; the truth (observed
cross-stage residual correlations ≤ .32) is between. And M4 supplied the receipts that the
point-forecast version of this matters: the GBM's only extra information was other stages' lag-1
deviations, and it beat Tier 2's FIP points 3/4 (.7938 vs .8131) — a pitcher's K/BB/HR come from
one arsenal, not three independent walks. M2c declined the joint model on cost grounds with the
holdout waiting; that was a defensible scheduling decision, not a claim the assumption is right.

**A4. Four dev seasons cannot distinguish these models.** The H effect size is ~.0006 wOBA RMSE
(.0328 vs .0334, ~2%). The gate is a sign test with n=4 — it discards magnitude and its own
sampling noise exceeds the effect. Worse, the four targets aren't independent draws: 2021
(sticky stuff), 2022 (dead ball), 2023 (shift ban) are regime years whose common shocks hit all
players at once, so effective n < 4. The 2025 holdout then landed on Marcel's best year of the
five scored. Under this design, a true ~2% improvement was never reliably detectable; what the
gate *could* detect is a large win, and there wasn't one. Own this: the pre-registered gate was
the right discipline and the wrong statistic (year-counting instead of a paired by-player
bootstrap on the mean difference — which the memo already proposes for next time). Do not claim
the model "really won" on the mean; say the design couldn't resolve differences this small, and
that itself is a finding about h=1 projection.

**A5. The fits that produce the shipped bands are not fully converged.** Production: max r̂ 1.16
(H/k), 89 divergences (69 on P/bb); holdout fits reached r̂ 1.27 (`meta.json`, `M2_experiments.md`).
The project's own warning line is 1.05. Defense, honestly bounded: r̂ is over the *scalar
population parameters*, the ones the bands lean on; the divergences concentrate in known low-tau
funnel geometry (M1-F5), E5 removed most of them (313→121 dev), and the calibration these fits
imply passed a holdout. But a Bayesian shop will correctly say "your ESS on H/k is suspect, so
your q10 on a K-band is suspect." The truthful posture: known, diagnosed, bounded, unfixed —
reparameterisation of the low-tau chain is the named next step.

**A6. The hitter park_sd (.358) vs pitcher park_sd (.122) asymmetry is itself evidence of
confounding.** The physical park is the same for both roles; if phi were purely physics the
spreads should be comparable. The gap says hitter phi partially absorbs roster construction
(teams fit hitters to parks far more than pitchers). That contamination is *fine for projection*
(the roster effect is real and persistent) but it means "phi = park effect" is an overclaim; call
it a venue-associated effect. Related presentation bug in §B2.

**A7. Window_end is a partial season.** Production fits end at 2026 with the season ~95%
complete (data through 2026-09-18, PA totals ~5% light in `CONTEXT.md` §4). The PT model's s1
feature and the last talent observation are both slightly depressed for anyone still playing.
Documented (README says re-run after the season), but a live-fire question if they poke at
Judge's 285 PA.

## B. Everything my inspection found that does not line up — ranked by interview damage

1. **The waterfall and the headline projection disagree on the same page.** `waterfall_frame`
   uses raw (unanchored) Tier 2 draws; `projections_frame` ships Marcel-anchored draws. Judge:
   waterfall ends "At home park .385", the stat table/fan chart say h1 q50 .418. Across H/wOBA:
   mean gap −.018, max .088 (computed this prep). Nothing on the player page or Methodology says
   the waterfall walks the *Tier 2* chain while the headline is Marcel. An analyst will see this
   in five minutes. Answer if asked: the waterfall is the Bayesian model's decision chain
   (deliberately, it explains the machinery), the headline is the shipped Marcel-anchored number;
   the gap between step 5 and the headline *is* the Marcel anchor. But the UI should say that,
   and today it doesn't. (Filed to HANDOFF.)
2. **"Top HR parks" displays negative phi under "positive = HR-friendly."** `meta.json` top 3:
   Yankee Stadium +0.021, Dodger Stadium −0.140, Great American −0.176; bottom: Kauffman −0.785.
   The phi vector is uncentred — a constant shift in all phi is unidentified against the talent
   level (every player carries total exposure 0.5), so only *differences* between parks are
   meaningful, and the Methodology page presents raw levels with a sign interpretation they
   don't support. GABP listed as a "top" park at −0.18, Kauffman at an implausible ×0.68 home HR
   factor. Say: "ranking valid, levels not identified, display should centre phi." (HANDOFF.)
3. **Methodology's Limitations bullet says "Projections are park-neutral"** on the same page
   that describes park-aware scoring (M1) and above a waterfall whose final step is "At home
   park." Stale — approximately true for shipped *points* under the Marcel anchor, false as a
   blanket statement. (HANDOFF.)
4. **The Fable context pack contradicts the artifacts it ships next to.** `CONTEXT.md`
   (regenerated 2026-09-18 22:20, *after* the holdout) says "Holdout 2025 is unspent," shows the
   pre-M2 model equations with no sigma_obs, and says "Projections park-neutral, conditional on
   playing (no attrition model)" — all three superseded. Cause: hard-coded strings in
   `diagnostics.py` (lines ~670, ~679). Anyone reading the repo top-down hits this. (HANDOFF.)
5. **Sampler health vs the shipped claim** — the §A5 numbers (r̂ 1.16 / 89 div in the very fits
   that produce the bands; RHAT_WARN=1.05 in the code). Documented in memo/README, so it's a
   soft spot, not a hidden one.
6. **Band-narrowing vs the project's own targets.** `project.py`'s spot check still prints
   against a ">95% widen" target that actual artifacts hit at 17.6% (H wOBA); the sim smoke test
   (`test_state_space.py`) asserts widening >90% and passes only because sim tau is large.
   Diagnosed as not-a-bug (check A) but the acceptance text was never restated, so the code
   contradicts the diagnosis it links to.
7. **Two different playing-time numbers ship simultaneously.** Leaderboard/headline `pt` is
   Marcel (Judge 410); the outlook's `pt_expected` is the hurdle (Judge 545) — after M3
   concluded the hurdle strictly dominates 8/8. Methodology admits the split. The honest reason
   is wiring order and leaderboard compatibility, but "your own site shows two PTs for the same
   player and you validated one of them as better" is a fair hit.
8. **ERA is literally FIP.** `derived_stats` sets `era = fip` for every pitcher; StatTable
   displays both columns, identical to the third decimal. Defensible convention (league FIP ==
   league ERA by construction of cFIP), but two identical columns with different headers looks
   like a bug until explained.
9. **Tests cover leakage superbly and the shipping transform not at all.** The leakage tests are
   genuinely strong (end-to-end data poisoning, mutation-checked guards, M4 mirror). But there is
   no test for `_anchor_to_marcel` (the one transform between the validated model and every
   shipped number), none for `waterfall_frame`/`aging_frame`, and the M2c "locked config" tests
   assert CLI flag plumbing via monkeypatched stubs — they verify wiring, not statistics. "65
   tests pass" (verified this prep) overstates model-level coverage.
10. **Doc rot, small but visible:** `marcel.py`/`league.py` docstrings cite `test_marcel.py`/
    `test_league.py` (neither exists; it's `test_marcel_league.py`); `state_space.py`'s header
    advertises the simulation's "0 divergences" two files away from production meta showing 89;
    M3's raw tables cite `/tmp/*.csv` paths that no longer exist (though `make pt-backtest`
    reproduces §7 to the digit, which is the better citation); p_regular is non-monotonic across
    horizons for Judge (.852/.832/.847/.834 — simulation noise, only h1 is shown).

Nothing I checked in the *numbers* failed: every headline figure in the memo, README, M2/M3/M4
docs and Methodology reproduced from the committed artifacts (dev means, holdout rows, M4 RMSE/
CRPS tables, PT tables, tau/sigma_obs values). The discrepancies above are presentation, staleness
and validation-scope issues — real, but there is no number in the docs I could not re-derive.

## C. The ten most likely questions, with answers

**1. "Why should we care about a model that lost to Marcel?"**
Because the deliverables that shipped are the ones that won their tests: calibrated intervals
(holdout cov80 .83/.75, 9/10 rows in band — Marcel produces no intervals), a playing-time model
that beat its baseline 8/8 with bias +126 PA → +3, and per-stat reliability learned from data.
And because the negative result is measured under rules written before the runs — which is the
working style you're actually hiring. [`backtest.json`, `M3_playing_time.md`, `M2_experiments.md`]

**2. "Your waterfall says .385 for Judge; your table says .418. Which is your projection?"**
.418. The waterfall walks the Bayesian model's own chain — 3-year line, regression, aging, park —
and its endpoint is the Tier 2 median; production then anchors medians to Marcel because Marcel
won the points gate, and the anchor is the −.018 average gap you're seeing. It's a real
presentation flaw that the page doesn't label the waterfall as the model's chain rather than the
shipped number — flagged and queued. [computed from `waterfall.parquet` vs `projections.parquet`]

**3. "You validated Tier 2 coverage, then shipped those bands around different points. Where's
the coverage number for the shipped object?"**
It doesn't exist; that's a fair catch (§A1). The argument is that the anchor centres bands on a
point with equal-or-better RMSE, which shouldn't hurt coverage; the measurement — re-scoring
cov80 with the sidecar bands re-centred on Marcel across 2021–24 — is cheap and is the first
thing I'd run next. I'd rather concede a missing measurement than defend it as validated.

**4. "GABP is a top HR park in your meta with phi = −0.18, and Kauffman is −0.785?"**
The phi *level* is not identified — every player carries total park exposure 0.5, so a constant
shift in all phi trades off against the talent level; only differences are meaningful, and the
display should have centred them. The ranking (Yankee high, Kauffman low) and the spreads
(park_sd .358 H/hr) are the identified content. Also honest: hitter phi partially absorbs roster
fit — teams stock hitters for their park — which is why hitter park_sd (.358) is 3× pitchers'
(.122) for the same physical parks. [`meta.json`]

**5. "Why do Judge's bands get narrower four years out? You know less, not more."**
In logit space we do know less — sd widens h1→h4 for 96–100% of players on every stage. The
rate-space band contracts because the level falls with age and a binomial band scales with
p(1−p): a ~15% lower HR rate shrinks the band ~15% while drift only adds ~9%. It's bounded-scale
geometry, not confidence. And because nothing beyond h1 is backtested, the UI marks h2–h4
"model-implied, not backtested." [`STATUS.md` artifact check A]

**6. "n=4 targets, a 3-of-4 sign test, ~2% effect size. What power did that gate ever have?"**
Close to none for effects this small — and the targets share regime shocks (sticky stuff, dead
ball, shift ban), so effective n < 4. The gate was pre-registered before we knew the effects
would be this small, and we kept it rather than move goalposts after seeing numbers; the
documented recommendation is a paired by-player block bootstrap on the mean difference next
time. The right conclusion isn't "the model secretly won" — it's that at h=1 the recoverable
edge over well-tuned shrinkage is small enough that this design can't resolve it.
[`M2_experiments.md` "The mean and the gate disagree"]

**7. "Why did Statcast make it worse?"**
Tier 3 tied K/BB (no indicator), and on the mapped stages it *hurt* points: H HR% .0155 → .0171
vs Tier 2 (pre-M2 config). The indicator is a second likelihood on the same theta — barrels/BBE
measures HR talent faster, so the posterior tracks Barrel% swings, and hitter Barrel% over
4-season windows is itself noisy: it dragged projections toward one noisy fast signal faster
than Marcel's regression dragged toward the multi-year mean. Geometry improved (target_accept
.95, divergences 313 → 96), points didn't. It failed a fair test and didn't ship; with obs-noise
now in the model, re-testing Tier 3 on the locked config is a legitimate next experiment.
[`STATUS.md` P6]

**8. "Your pitcher stages are three independent walks. A pitcher has one arsenal."**
Agreed, and we have quantitative evidence it costs us: M4's GBM, whose only extra information
was other stages' lag-1 deviations, beat Tier 2's FIP points 3/4 (.7938 vs .8131) and its CRPS
3/4 — on hitters, with the same edge available, it lost everything, so the effect is
pitcher-specific cross-stage signal, exactly what a shared arsenal factor would capture. M2c
declined the joint rebuild on cost with the holdout pending; it's first on the "what next" list,
gated on a pre-registered 2026-target score. [`M4_ml_challenger.md` §6–7]

**9. "Judge played 285 PA this year. Marcel says 410. You say 545. Defend that."**
The hurdle with talent says a .419-wOBA hitter whose *team wants him on the field* gets his PT
back: p_play .96, and conditional-on-playing volume near his healthy norm. The pattern was
validated in aggregate, not on Judge: for regular hitters the talent-free hurdle was −65 PA
biased and Marcel +4; adding the shrunk-wOBA covariate cut the hurdle bias to −18 and won the
pre-registered RMSE gate 8/8. Marcel's 410 is .5×285+.1×679+200 — it has no way to know 285 was
an injury season by a great hitter rather than decline by an ordinary one. The caveat I'll
volunteer: at h2+ the simulation feeds its own healthy seasons back as features, so his PT
*rises* with age (545→646) — which is why the product shows PT for year 1 only.
[`M3_playing_time.md` §7–8]

**10. "What's the one thing you'd fix in the Bayesian model before adding anything?"**
The low-tau chain geometry. sigma_pop .09 / tau .01 on BABIP makes theta's cumulative-sum
parameterisation collapse (M1-F5): that's where the divergences live, r̂ 1.16 production /
1.27 holdout, and it's load-bearing because the bands are the shipped deliverable. Marginalise
or reparameterise (player-constant talent + small AR term for near-static stages) before any
new structure — you shouldn't grow a model whose posterior you can't reliably sample.
[`M1_audit.md` F5, `meta.json`]

## D. "So why didn't it work?" — the honest mechanical answer

Give the mechanism, not a shrug. Four parts:

1. **The residual Marcel leaves is mostly unforecastable.** At h=1, wOBA error decomposes into
   binomial sampling noise at 400–700 PA (irreducible), common league-environment shifts
   (2021 sticky stuff, 2022 dead ball — unforecastable by construction; both models ate them),
   genuine talent breaks (injury, mechanics — invisible to both), and a thin slice of
   recoverable structure. Marcel's 5/4/3 + 1,200-PA regression + age bump is already a decent
   approximation to the optimal filter for that structure. The full hierarchical model's
   measured edge over it on hitters was .0334 → .0328 — real, ~2%, and smaller than one season's
   sampling noise in a 4-target design (§A4). On pitchers it lost outright (.8164 vs .7947).

2. **Where our structure differed from Marcel's, it started out wrong in three specific ways,
   and we found each one:** the walk forced all year-to-year variance to persist → T−1 chasing
   on the stablest skills (fixed by sigma_obs, E5); the league environment point was a flat
   3-year mean that lagged trends worse than Marcel's 5/4/3 implicitly does (variance priced by
   E6; point still stale — the 2022 FIP loss is mostly this); relievers pooled into a
   starter-dominated prior (diagnosed, E3 rejected on an unverifiable mechanism check + a 1.363
   r̂). After the fixes, the hitter model was slightly better on the mean and the pitcher model
   still lost — because FIP triples BB% weight and 13×'s HR, concentrating exactly the
   environment-regime and cross-stage weaknesses we hadn't fixed.

3. **The component story shows the machinery works where its assumptions bind.** Tier 2 wins
   BABIP for both roles, K% for both, pitcher HR — the high-noise stats where learned shrinkage
   is the whole job — and the pattern replicated on the untouched holdout (5 of 8 component
   rows). It loses on the aggregate because wOBA/FIP re-weight components toward the ones where
   shrinkage isn't the binding constraint. That's not an excuse — we chose the key stats in
   advance because they're what a club buys — but it locates the failure precisely: aggregation
   weights × environment regime error × cross-stage independence, not "Bayes doesn't work."

4. **And say what did work, because it's the same machinery:** the identical posterior that
   couldn't beat Marcel's point produced 80% intervals that covered .83/.75 on a one-shot
   holdout, per-stat reliabilities that reproduce known stabilization behavior including DIPS,
   and the hurdle model beat its baseline 8 of 8 the first time a baseline was actually weak.
   The system failed exactly where the baseline was near-optimal and succeeded wherever the
   baseline had a structural hole. That is what you'd predict if the methodology is sound and
   the h=1 point-projection margin in this sport is simply thin — which is, itself, the most
   defensible thing this project learned.

---

## Cheat sheet (all committed numbers)

| fact | number | file |
|---|---|---|
| Dev H wOBA (Marcel / Tier 2), wins | .0334 / .0328, 2/4 (need 3), cov80 .819 | backtest.json |
| Dev P FIP (Marcel / Tier 2), wins | .7947 / .8164, 1/4, cov80 .761 | backtest.json |
| Holdout 2025 H wOBA / P FIP | .0305/.0309 (.83) · .7317/.7399 (.75) | M2_experiments.md |
| sigma_pop: H k / H babip / P babip | .359 / .091 / .047 | meta.json |
| tau: H k / H bb / H babip | .104 / .089 / .0105 | meta.json |
| sigma_obs H bb; tau fall | .13; .129 → .061 | M2_experiments.md M2c |
| Park fix (M1) | H hr .0155→.0128; H wOBA .0364→.0333 | M1_audit.md, STATUS.md |
| park_sd H/hr vs P/hr | .358 vs .122 | meta.json |
| PT hurdle vs Marcel | 8/8; H −25% P −11%; bias +126→+3 PA | M3_playing_time.md |
| Judge PT (Marcel / base / +talent) | 410 / 258 / 545, p_play .78→.96 | M3 §7 |
| Regulars bias H (Marcel/base/talent) | +4 / −65 / −18 PA | M3 §8 |
| M4 P FIP (gbm/tier2/marcel) | .7938 / .8131 / .7947; hybrid .7770 ('22–24) | M4 §6 |
| Production sampler health | max r̂ 1.16, 89 div (69 P/bb); holdout r̂ 1.27 | meta.json, M2 doc |
| Bands widen h1→h4 (H wOBA finite) | 17.6% rate-space; 96–100% logit-space | STATUS check A |
| Marcel anchor shift (H wOBA h1) | mean −.018, max .088 | computed, this prep |
| Divergences: pre-E5 → E5 → prod | 313 → 121 → 89 | STATUS, meta.json |
