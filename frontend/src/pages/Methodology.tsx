import { useEffect, useState } from 'react'
import { api, type Backtest, type Meta } from '../api'
import { fmtStat, statLabel, ratio2 } from '../format'

const KEY_STATS: Record<'H' | 'P', string[]> = {
  H: ['woba', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
  P: ['fip', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
}

type StageSummary = {
  tau_mean?: number | null
  sigma_obs_mean?: number | null
  sigma_env?: number | null
  sigma_pop_mean?: number | null
  park_sd_mean?: number | null
  max_rhat?: number | null
  divergences?: number | null
  top_hr_parks?: Array<{ venue_id: number; venue_name: string; phi: number }>
  bottom_hr_parks?: Array<{ venue_id: number; venue_name: string; phi: number }>
}

const fmt3 = (x: number | null | undefined) => (x !== null && x !== undefined ? x.toFixed(3) : '—')

function mean(xs: number[]): number | null {
  const clean = xs.filter(Number.isFinite)
  if (clean.length === 0) return null
  return clean.reduce((a, b) => a + b, 0) / clean.length
}

// Development scoring excludes the holdout season, which is reported on its own below.
function summariseBacktest(bt: Backtest, role: 'H' | 'P', target?: number): { stat: string; marcel: number | null; tier2: number | null; tier3: number | null; cov80_t2: number | null; cov80_t3: number | null }[] {
  if (!bt) return []
  const stats = KEY_STATS[role]
  const rows = bt.rows.filter(r => r.role === role && r.stat && r.stat !== '_diagnostics'
    && (target !== undefined ? r.target === target : r.target !== bt.holdout_target))
  return stats.map(stat => {
    const subset = (tier: string) => rows.filter(r => r.tier === tier && r.stat === stat)
    return {
      stat,
      marcel: mean(subset('marcel').map(r => r.rmse ?? NaN)),
      tier2: mean(subset('tier2').map(r => r.rmse ?? NaN)),
      tier3: mean(subset('tier3').map(r => r.rmse ?? NaN)),
      cov80_t2: mean(subset('tier2').map(r => r.cov80 ?? NaN)),
      cov80_t3: mean(subset('tier3').map(r => r.cov80 ?? NaN)),
    }
  })
}

function StageTable({ stages, roleTag }: { stages: Record<string, StageSummary>; roleTag: 'H' | 'P' }) {
  const entries = Object.entries(stages).filter(([k]) => k.startsWith(`${roleTag}/`))
  if (entries.length === 0) return null
  return (
    <table>
      <thead>
        <tr>
          <th>Stage</th>
          <th className="numeric">τ</th>
          <th className="numeric">σ_obs</th>
          <th className="numeric">σ_env</th>
          <th className="numeric">σ_pop</th>
          <th className="numeric">park_sd</th>
          <th className="numeric">max r̂</th>
          <th className="numeric">divergences</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td>{k.split('/')[1]}</td>
            <td className="numeric">{fmt3(v.tau_mean)}</td>
            <td className="numeric">{fmt3(v.sigma_obs_mean)}</td>
            <td className="numeric">{fmt3(v.sigma_env)}</td>
            <td className="numeric">{fmt3(v.sigma_pop_mean)}</td>
            <td className="numeric">{fmt3(v.park_sd_mean)}</td>
            <td className="numeric">{fmt3(v.max_rhat)}</td>
            <td className="numeric">{v.divergences ?? 0}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function BacktestTable({ bt, role, label }: { bt: Backtest; role: 'H' | 'P'; label: string }) {
  const rows = summariseBacktest(bt, role)
  const gates = bt?.gates?.[role] ?? {}
  return (
    <div>
      <h3>{label}</h3>
      <table>
        <thead>
          <tr>
            <th>Stat</th>
            <th className="numeric">Marcel RMSE</th>
            <th className="numeric">Tier 2 RMSE</th>
            <th className="numeric">Tier 3 RMSE</th>
            <th className="numeric">Tier 2 cov80</th>
            <th className="numeric">Tier 3 cov80</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.stat}>
              <td>{statLabel(r.stat)}</td>
              <td className="numeric">{r.marcel !== null ? fmtStat(r.stat, r.marcel) : '—'}</td>
              <td className="numeric">{r.tier2 !== null ? fmtStat(r.stat, r.tier2) : '—'}</td>
              <td className="numeric">{r.tier3 !== null ? fmtStat(r.stat, r.tier3) : '—'}</td>
              <td className="numeric">{r.cov80_t2 !== null ? r.cov80_t2.toFixed(2) : '—'}</td>
              <td className="numeric">{r.cov80_t3 !== null ? r.cov80_t3.toFixed(2) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
        {Object.entries(gates).map(([tier, g]) => {
          const gObj = g as { pass?: boolean; wins?: number; of?: number; cov80_mean?: number; vs?: string } | boolean | null
          if (typeof gObj !== 'object' || gObj === null) return null
          return (
            <div key={tier}>
              Gate {tier} vs {gObj.vs}: <strong>{gObj.pass ? 'PASS' : 'FAIL'}</strong> ({gObj.wins}/{gObj.of} target wins; mean cov80 {gObj.cov80_mean !== undefined ? gObj.cov80_mean.toFixed(2) : '—'})
            </div>
          )
        })}
      </div>
    </div>
  )
}

function HoldoutTable({ bt, target }: { bt: Backtest; target: number }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Role</th>
          <th>Stat</th>
          <th className="numeric">Marcel RMSE</th>
          <th className="numeric">Tier 2 RMSE</th>
          <th className="numeric">Tier 2 cov80</th>
        </tr>
      </thead>
      <tbody>
        {(['H', 'P'] as const).flatMap(role => summariseBacktest(bt, role, target).map(r => (
          <tr key={`${role}-${r.stat}`}>
            <td>{role}</td>
            <td>{statLabel(r.stat)}</td>
            <td className="numeric">{r.marcel !== null ? fmtStat(r.stat, r.marcel) : '—'}</td>
            <td className="numeric">{r.tier2 !== null ? fmtStat(r.stat, r.tier2) : '—'}</td>
            <td className="numeric">{r.cov80_t2 !== null ? r.cov80_t2.toFixed(2) : '—'}</td>
          </tr>
        )))}
      </tbody>
    </table>
  )
}

export default function Methodology() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [bt, setBt] = useState<Backtest>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.meta().then(r => { setMeta(r.meta); setBt(r.backtest) }).catch(e => setErr(String(e)))
  }, [])

  if (err) return <div className="error">{err}</div>
  if (!meta) return <div className="loading">Loading…</div>

  const stages = (meta.stages ?? {}) as Record<string, StageSummary>
  const hHitBip = stages['H/hit_bip']
  const pHitBip = stages['P/hit_bip']
  const hrParks = stages['H/hr']
  const holdoutTarget = bt?.holdout_target ?? null
  const holdoutRows = bt?.rows.filter(r => r.target === holdoutTarget) ?? []
  const devTargets = (bt?.targets ?? []).filter(t => t !== holdoutTarget)
  const devSpan = devTargets.length ? `${Math.min(...devTargets)}–${Math.max(...devTargets)}` : '2021–2024'
  const cov = (role: 'H' | 'P') => {
    const g = bt?.gates?.[role]?.tier2 as unknown as { cov80_mean?: number } | null | undefined
    return g?.cov80_mean !== undefined ? g.cov80_mean.toFixed(2) : '—'
  }
  const cfg = meta.model_config

  return (
    <div className="methodology">
      <h1>Methodology</h1>
      <p className="muted">Bayesian hierarchical projections of MLB hitters and pitchers, component by component.</p>

      <h2>Overview</h2>
      <p>
        KEYSTONE decomposes each plate appearance into a chain of conditional binomials
        (strikeout, unintentional walk, HBP, then HR / BABIP / extra-base hits on contact).
        A separate state-space model is fit per component, so the amount of regression to
        the mean is learned from the data one stat at a time — K% shrinks little (very
        reliable) while BABIP shrinks a lot (very noisy). Every projection carries a
        posterior distribution, and we score the intervals honestly against held-out seasons.
      </p>

      <h2>Component stages</h2>
      <table>
        <thead>
          <tr><th>Stage</th><th>Successes / trials</th><th>Park?</th></tr>
        </thead>
        <tbody>
          <tr><td>K</td><td>K / PA'</td><td>no</td></tr>
          <tr><td>BB</td><td>uBB / (PA' − K)</td><td>no</td></tr>
          <tr><td>HBP</td><td>HBP / (PA' − K − uBB)</td><td>no</td></tr>
          <tr><td>HR</td><td>HR / contact PA</td><td>yes</td></tr>
          <tr><td>BABIP</td><td>(H − HR) / BIP</td><td>yes</td></tr>
          <tr><td>XBH (H only)</td><td>(2B + 3B) / (H − HR)</td><td>yes</td></tr>
          <tr><td>3B (H only)</td><td>3B / (2B + 3B)</td><td>yes</td></tr>
        </tbody>
      </table>
      <p className="muted" style={{ fontSize: 12 }}>PA' = PA − IBB − SH − CI. Pitchers use BF' analogously.</p>

      <h2>Tier 1 — Marcel</h2>
      <p>
        5/4/3 (hitters) or 3/2/1 (pitchers) weighted three-year average, regressed with 1,200 PA'
        or BF' toward league, aged +0.006 per year under 29 and −0.003 per year above. Playing
        time from PA₁·0.5 + PA₂·0.1 + 200 (or the pitcher analogue). Simple, hard to beat, no
        uncertainty.
      </p>

      <h2>Tier 2 — Bayesian state-space model</h2>
      <p>For each (role, stage), fit on the last six seasons:</p>
      <pre>{`theta[i, first] = lam · z(log PA'_first) + sigma_pop · e
theta[i, t]     = theta[i, t-1] + g[age] + tau · e
y[i, t]         ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t] + X_park · phi + sigma_obs · eps[i, t]))`}</pre>
      <ul>
        <li><code>mu_league[t]</code>: the fixed league logit from that season (juiced ball, rule changes, etc.).</li>
        <li><code>tau</code>: talent drift — effectively a learned recency weight per stat.</li>
        <li><code>sigma_pop</code>: true-talent spread across the population.</li>
        <li><code>g[age]</code>: a smooth aging curve fit jointly across all seasons (not delta-method paired seasons).</li>
        <li><code>phi</code>: park effects on the park stages, with 0.5 · share exposure per team.</li>
        <li><code>sigma_obs</code>: transient season-level noise, fitted per stage and not carried forward.</li>
      </ul>
      <p>
        A transient season-level noise term (<code>sigma_obs</code>) separates single-season wiggle
        from talent drift, so a one-year spike no longer has to be explained as a change in true
        talent. Projection intervals also carry a common league-environment shock
        (<code>sigma_env</code>, the sd of year-over-year changes in the league rate), because
        next season's league level is itself uncertain and moves every player together.
        {cfg && (
          <span className="muted"> Production config: <code>obs_noise = {String(cfg.obs_noise)}</code>,{' '}
            <code>env_mode = {cfg.env_mode}</code>.</span>
        )}
      </p>
      <p>
        Sampled with nutpie: 500 draws × 4 chains in production, target_accept = 0.9. Stage
        posteriors are combined index-by-index (an approximation that ignores between-stage
        correlation) to get wOBA/FIP.
      </p>

      <h2>Tier 3 — Statcast contact quality</h2>
      <p>
        Optional per stage: adds a second binomial likelihood tied to the same latent talent —
        barrels/attempts for HR (both roles), 95+ mph BBE / attempts for hitter BABIP.
        target_accept moves to 0.95 to keep the funnel healthy.
      </p>
      <p>
        The Tier 3 indicator was built and backtested but did not earn a place in the
        production projection (it lost to Tier 2 on points). The player-page waterfall
        therefore shows the four steps that are actually in the shipped path — 3-year line,
        regression to the mean, aging (which is also the neutral-park projection), and home
        park.
      </p>

      <h2>What the model learned</h2>
      <p>Stage parameters, hitters:</p>
      <StageTable stages={stages} roleTag="H" />
      <p style={{ marginTop: 16 }}>Stage parameters, pitchers:</p>
      <StageTable stages={stages} roleTag="P" />
      {hHitBip && pHitBip && hHitBip.sigma_pop_mean && pHitBip.sigma_pop_mean && (
        <p style={{ marginTop: 12 }}>
          <strong>DIPS falls out of the fit.</strong> Pitcher BABIP σ<sub>pop</sub> ={' '}
          <code>{pHitBip.sigma_pop_mean.toFixed(3)}</code>, hitter BABIP σ<sub>pop</sub> ={' '}
          <code>{hHitBip.sigma_pop_mean.toFixed(3)}</code>. Pitchers' true-talent spread on BABIP
          is roughly {ratio2((pHitBip.sigma_pop_mean / hHitBip.sigma_pop_mean) * 1)}× the hitter
          spread, i.e. pitchers own far less of their BABIP than hitters do.
        </p>
      )}
      {hrParks?.top_hr_parks && hrParks?.bottom_hr_parks && (() => {
        // φ's level is unidentified — a constant shift trades off against theta (each
        // player's total park exposure sums to 0.5), so only differences between parks
        // are meaningful. Render Δφ relative to the mean of the six reported parks.
        // The next `make project` will emit φ already centred (project.meta_dict).
        const all = [...hrParks.top_hr_parks, ...hrParks.bottom_hr_parks]
        const bar = all.reduce((a, p) => a + p.phi, 0) / all.length
        const already = Math.abs(bar) < 1e-6
        const disp = (p: { phi: number }) => (already ? p.phi : p.phi - bar)
        return (
          <div>
            <p style={{ marginTop: 12 }}>
              Top/bottom HR parks — Δφ vs the mean of the six shown (hitter HR stage). Only
              differences between parks are identified: a common shift in φ trades off against
              the talent term, so we report Δφ, not raw φ. Positive Δφ ≡ HR-friendlier than the
              typical park in this list.
            </p>
            <table>
              <thead><tr><th>Park</th><th className="numeric">Δφ</th></tr></thead>
              <tbody>
                {hrParks.top_hr_parks.map(p => {
                  const v = disp(p)
                  return <tr key={`t-${p.venue_id}`}><td>{p.venue_name}</td><td className="numeric">{v >= 0 ? '+' : ''}{v.toFixed(3)}</td></tr>
                })}
                {hrParks.bottom_hr_parks.map(p => {
                  const v = disp(p)
                  return <tr key={`b-${p.venue_id}`}><td>{p.venue_name}</td><td className="numeric">{v >= 0 ? '+' : ''}{v.toFixed(3)}</td></tr>
                })}
              </tbody>
            </table>
          </div>
        )
      })()}
      <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        Sampler health across production fits: max r̂ = {meta.max_rhat?.toFixed(3)}, total divergences = {meta.total_divergences}.
      </p>

      <h2>Playing time and the multi-year outlook</h2>
      <p>
        Headline PA/IP and the leaderboard still use Marcel playing time. The multi-year outlook uses
        a Bayesian hurdle model fit per role: one part gives the chance a player gets any MLB time
        that season, and the other gives how much time he gets if he plays. Features are last
        year's and the year before's playing time, age and a missed-time proxy, plus starter
        share for pitchers, plus a talent term: the playing-time-weighted wOBA (hitters) or
        FIP-core (pitchers) gap to league over the last two seasons, shrunk by one full season
        (600 PA / 180 IP) of league-average ballast. Talent is held fixed across the four
        simulated seasons; aging enters only through the age terms. The model is simulated forward four seasons, and a player can return
        after missing a year. Per season it reports <code>p_play</code> (chance of any MLB time),
        expected PA/IP including the zero outcome, and the chance he is still a regular
        (≥ 300 PA / 100 IP).
      </p>
      <p>
        <strong>Expected production = P(plays) × the conditional projection.</strong> Counting stats
        scale by expected playing time. Rate stats are unchanged, and the player page labels them
        with the chance he plays. This assumes playing time and rate are independent given the
        covariates. That is wrong in detail: players who lose time are usually declining. So
        expected counting production is still slightly optimistic for decliners. The line
        labelled "if he plays" keeps its meaning of conditional on playing.
      </p>
      <p>
        <strong>Beyond year 1, intervals are model-implied, not backtested.</strong> The backtest
        scores horizon 1 only. The h2–h4 bands follow from the fitted talent drift, and nothing
        has checked their calibration.
      </p>
      <p>
        <strong>Playing time is shown for year 1 only.</strong> Because teams give good players
        playing time, a star coming off a short season projects high again at year 1 (e.g. Aaron
        Judge after 285 PA in 2026: 96% chance he plays, about 545 expected PA). The hurdle model is
        backtested at h1 only (<code>make pt-backtest</code>). At h2+ it feeds its own simulated
        healthy seasons back in as the recent-PT feature, so expected playing time rises with age
        for players whose recent PT was injury-depressed: Judge goes 545 / 579 / 620 / 646 PA from
        age 35 to 38 while his wOBA correctly declines from .419 to .369. We do not display a number
        we have not validated, so the outlook shows rates only for years 2–4.
      </p>
      <p>
        <strong>Validation (M3).</strong> On the same population and actuals, the hurdle beat
        Marcel playing time on RMSE in 8 of 8 dev targets (2021–2024; pre-registered gate ≥ 3 of 4
        per role). RMSE fell 25% for hitters and 11% for pitchers. Marcel's mean over-projection
        of about +126 PA / +22 IP per player-season fell to about +3 PA / +1 IP. The per-target
        table is in <code>docs/fable/M3_playing_time.md</code> §3. Adding the talent term
        (pre-registered follow-up, §7) lowered RMSE again in 8 of 8 dev targets and moved the
        bias for age ≥ 33 top-quartile-talent players toward zero in 4 of 4; the shipped model
        includes it, and <code>make pt-backtest</code> reproduces the §7 numbers. The 2025
        holdout was not used.
      </p>

      <h2>Validation</h2>
      <p>
        Rolling-origin backtests on {devSpan} (window_end = T−1). Point projections are Tier 2/3
        posterior means at horizon 1; Marcel is Marcel. Metrics are averaged across targets.
        Intervals use <code>simulate_season</code> at each player's actual PA'/BF' (pitcher FIP
        uses actual IP).
      </p>
      <p className="muted" style={{ fontSize: 12 }}>
        As of M1, backtest scoring is park-aware: Tier 2/3 projections are evaluated in the
        player's last-season park, matching the park information Marcel carries implicitly through
        raw rates. See <code>backtest.json.park_aware_scoring</code>.
      </p>
      {bt ? (
        <>
          <BacktestTable bt={bt} role="H" label="Hitters" />
          <div style={{ marginTop: 16 }}>
            <BacktestTable bt={bt} role="P" label="Pitchers" />
          </div>
          <p style={{ marginTop: 12 }}>
            Production tier: <strong>H = {bt.production_tier.H}</strong>,{' '}
            <strong>P = {bt.production_tier.P}</strong>.
            {' '}Where Tier 2 fails, production ships Marcel points with Tier 2 bands (§6).
          </p>
          <p>
            <strong>Model iteration (M2).</strong> The original Tier 2 intervals were too narrow
            for pitchers. Two changes were tested against pre-registered expectations and accepted: the
            season-level noise term and the league-environment shock. A recency-weighted league
            point, fat-tailed talent innovations and a reliever effect were rejected, and correlated
            stages were considered but not built. Mean 80% coverage is now in
            the [.75, .85] band for both roles (H {cov('H')}, P {cov('P')}). Point accuracy still does not
            clear the gate against Marcel, so shipped points remain Marcel's. The configuration was
            locked and committed before any {holdoutTarget ?? 2025} number was computed.
          </p>
          {holdoutTarget !== null && (holdoutRows.length === 0 ? (
            <p>Holdout target: {holdoutTarget}. Unspent — reserved for after model iteration.</p>
          ) : (
            <div style={{ marginTop: 16 }}>
              <h3>{holdoutTarget} holdout (scored once, locked config)</h3>
              <HoldoutTable bt={bt} target={holdoutTarget} />
              <p style={{ marginTop: 12 }}>
                On the untouched {holdoutTarget} season, Tier 2 scored slightly <em>below</em> Marcel on
                both key stats (wOBA and FIP RMSE), while its 80% intervals stayed in band. One season
                can't settle the points question either way. It does confirm the one claim the
                shipped bands make, that they are calibrated.
              </p>
            </div>
          ))}
        </>
      ) : <div className="muted">No backtest available.</div>}

      <h2>Limitations</h2>
      <ul>
        <li>The outlook shows playing time for year 1 only, by design: at h2+ the hurdle model feeds its own simulated healthy seasons back in as recent PT, so injury-depressed stars' PT rises with age, and only h1 is backtested.</li>
        <li>Headline playing time is Marcel's. Attrition enters only through the multi-year outlook's hurdle model, which has no role-change or injury-report information.</li>
        <li>Stages are fit independently; between-stage correlation is ignored when combining.</li>
        <li>
          Park handling: park-aware draws ship for the batted-ball stages (hr, hit_bip, xbh, 3B),
          in each player's last-observed home park; the M1 backtest scores in that same park. The
          shipped h=1 <em>median</em> is Marcel-anchored (§6 fallback), so the park term nets out
          of the point projection but is present in the bands and in the waterfall's "At home
          park" step. Rate projections are conditional on the player playing; the outlook's
          "expected" line is not.
        </li>
        <li>
          Pitcher ERA in the projection tables is FIP re-labelled: league FIP = league ERA by
          construction of cFIP (see <code>league.pitcher_constants</code>), so the projected ERA
          column carries no information beyond FIP for a single player-season. Both are shown
          because different readers ask for different names.
        </li>
        <li>Survivor bias: the eval population is players with ≥ 200 PA'/BF' in T and any prior history.</li>
        <li>2026 data is through {meta.data_through} — the season is not complete; artifacts should be re-run after the regular season ends.</li>
      </ul>

      <h2>Data sources</h2>
      <ul>
        <li>MLB Stats API for player-team-season counts, bios, and venues, 2015–2026.</li>
        <li>FanGraphs Guts (wOBA/FIP constants), saved by hand from the Guts! page.</li>
        <li>Baseball Savant exit-velocity/barrel leaderboards via <code>pybaseball</code> (Tier 3 only).</li>
      </ul>
    </div>
  )
}
