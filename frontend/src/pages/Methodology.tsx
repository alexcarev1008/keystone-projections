import { useEffect, useState } from 'react'
import { api, type Backtest, type Meta } from '../api'
import { fmtStat, statLabel, ratio2 } from '../format'

const KEY_STATS: Record<'H' | 'P', string[]> = {
  H: ['woba', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
  P: ['fip', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
}

type StageSummary = {
  tau_mean?: number | null
  sigma_pop_mean?: number | null
  park_sd_mean?: number | null
  max_rhat?: number | null
  divergences?: number | null
  top_hr_parks?: Array<{ venue_id: number; venue_name: string; phi: number }>
  bottom_hr_parks?: Array<{ venue_id: number; venue_name: string; phi: number }>
}

function mean(xs: number[]): number | null {
  const clean = xs.filter(Number.isFinite)
  if (clean.length === 0) return null
  return clean.reduce((a, b) => a + b, 0) / clean.length
}

function summariseBacktest(bt: Backtest, role: 'H' | 'P'): { stat: string; marcel: number | null; tier2: number | null; tier3: number | null; cov80_t2: number | null; cov80_t3: number | null }[] {
  if (!bt) return []
  const stats = KEY_STATS[role]
  const rows = bt.rows.filter(r => r.role === role && r.stat && r.stat !== '_diagnostics')
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
            <td className="numeric">{v.tau_mean !== null && v.tau_mean !== undefined ? v.tau_mean.toFixed(3) : '—'}</td>
            <td className="numeric">{v.sigma_pop_mean !== null && v.sigma_pop_mean !== undefined ? v.sigma_pop_mean.toFixed(3) : '—'}</td>
            <td className="numeric">{v.park_sd_mean !== null && v.park_sd_mean !== undefined ? v.park_sd_mean.toFixed(3) : '—'}</td>
            <td className="numeric">{v.max_rhat !== null && v.max_rhat !== undefined ? v.max_rhat.toFixed(3) : '—'}</td>
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
y[i, t]         ~ Binomial(n[i, t], invlogit(mu_league[t] + theta[i, t] + X_park · phi))`}</pre>
      <ul>
        <li><code>mu_league[t]</code>: the fixed league logit from that season (juiced ball, rule changes, etc.).</li>
        <li><code>tau</code>: talent drift — effectively a learned recency weight per stat.</li>
        <li><code>sigma_pop</code>: true-talent spread across the population.</li>
        <li><code>g[age]</code>: a smooth aging curve fit jointly across all seasons (not delta-method paired seasons).</li>
        <li><code>phi</code>: park effects on the park stages, with 0.5 · share exposure per team.</li>
      </ul>
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
      {hrParks?.top_hr_parks && hrParks?.bottom_hr_parks && (
        <div>
          <p style={{ marginTop: 12 }}>Top/bottom HR parks (φ, hitter HR stage; positive = HR-friendly):</p>
          <table>
            <thead><tr><th>Park</th><th className="numeric">φ</th></tr></thead>
            <tbody>
              {hrParks.top_hr_parks.map(p => (
                <tr key={`t-${p.venue_id}`}><td>{p.venue_name}</td><td className="numeric">{p.phi >= 0 ? '+' : ''}{p.phi.toFixed(3)}</td></tr>
              ))}
              {hrParks.bottom_hr_parks.map(p => (
                <tr key={`b-${p.venue_id}`}><td>{p.venue_name}</td><td className="numeric">{p.phi >= 0 ? '+' : ''}{p.phi.toFixed(3)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        Sampler health across production fits: max r̂ = {meta.max_rhat?.toFixed(3)}, total divergences = {meta.total_divergences}.
      </p>

      <h2>Validation</h2>
      <p>
        Rolling-origin backtests on 2021–2024 (window_end = T−1). Point projections are Tier 2/3
        posterior means at horizon 1; Marcel is Marcel. Metrics are averaged across targets.
        Intervals use <code>simulate_season</code> at each player's actual PA'/BF' (pitcher FIP
        uses actual IP).
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
          {holdoutTarget !== null && (
            <p>
              Holdout target: {holdoutTarget}. {holdoutRows.length === 0
                ? 'Unspent — reserved for after model iteration.'
                : `Scored (${holdoutRows.length} rows).`}
            </p>
          )}
        </>
      ) : <div className="muted">No backtest available.</div>}

      <h2>Limitations</h2>
      <ul>
        <li>Playing time comes from Marcel — no attrition or role-change model.</li>
        <li>Stages are fit independently; between-stage correlation is ignored when combining.</li>
        <li>Projections are park-neutral and conditional on the player playing.</li>
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
