import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, type Meta, type PlayerResponse, type Role } from '../api'
import { fmtStat, fmtRange, statLabel } from '../format'
import FanChart from '../components/FanChart'
import ComponentPanel from '../components/ComponentPanel'
import Waterfall from '../components/Waterfall'
import AgingOutlook from '../components/AgingOutlook'
import StatTable from '../components/StatTable'

const SUMMARY_STATS: Record<Role, string[]> = {
  H: ['woba', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
  P: ['fip', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
}
const KEY_STAT: Record<Role, string> = { H: 'woba', P: 'fip' }
const PT_LABEL: Record<Role, string> = { H: 'PA', P: 'IP' }

function h1Quantiles(p: PlayerResponse, stat: string) {
  const list = p.projections[stat] ?? []
  const row = list.find(r => r.horizon === 1)
  return { q10: row?.q10 ?? null, q50: row?.q50 ?? null, q90: row?.q90 ?? null }
}

function isFin(v: number | null | undefined): v is number {
  return v !== null && v !== undefined && Number.isFinite(v)
}

// A player's h=1 predictive interval is defined conditional on PA. When the playing-time
// hurdle returns nothing (no MLB PT projected for the season), q10/q25/q75/q90 are undefined
// and the API returns null for them. Detect that here so tiles/charts render the point
// without pretending there's a band.
function h1BandUndefined(p: PlayerResponse, stats: string[]): boolean {
  for (const stat of stats) {
    const row = (p.projections[stat] ?? []).find(r => r.horizon === 1)
    if (row && (!isFin(row.q10) || !isFin(row.q90))) return true
  }
  return false
}

export default function Player() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const role = (params.get('role') as Role | null) ?? undefined
  const [data, setData] = useState<PlayerResponse | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setData(null); setErr(null)
    if (!id) return
    api.player(id, role).then(setData).catch(e => setErr(String(e)))
  }, [id, role])

  useEffect(() => { api.meta().then(r => setMeta(r.meta)).catch(() => {}) }, [])

  if (err) return <div className="error">{err}</div>
  if (!data || !meta) return <div className="loading">Loading player…</div>

  const bio = data.bio
  const currentRole = data.role
  const roles = String(bio.roles ?? '')
  const twoWay = roles.includes('H') && roles.includes('P')
  const windowEnd = Number(meta.window_end ?? 2026)
  const keyStat = KEY_STAT[currentRole]

  const setRole = (r: Role) => {
    const next = new URLSearchParams(params)
    next.set('role', r)
    setParams(next, { replace: true })
  }

  const age = bio.birth_date ? computeAge(bio.birth_date) : null
  const noH1Band = h1BandUndefined(data, SUMMARY_STATS[currentRole])
  const noH1BandNote = 'No MLB playing time projected, so no predictive interval at h=1.'

  return (
    <div>
      <div className="header">
        <h1>{bio.name}</h1>
        <div className="meta">
          {age !== null && <>Age {age} · </>}
          {bio.last_team_abbr ?? '—'} · {bio.primary_pos ?? ''} · B/T {bio.bats ?? '?'}/{bio.throws ?? '?'}
        </div>
        {twoWay && (
          <div className="role-toggle">
            <button className={currentRole === 'H' ? 'active' : ''} onClick={() => setRole('H')}>Hitter</button>
            <button className={currentRole === 'P' ? 'active' : ''} onClick={() => setRole('P')}>Pitcher</button>
          </div>
        )}
      </div>

      <div className="summary-cards">
        {(() => {
          const q = h1Quantiles(data, keyStat)
          return (
            <div className="card primary">
              <div className="label">{statLabel(keyStat)} (h=1)</div>
              <div className="val">{fmtStat(keyStat, q.q50)}</div>
              {isFin(q.q10) && isFin(q.q90)
                ? <div className="range">80%: {fmtRange(keyStat, q.q10, q.q90)}</div>
                : <div className="range muted">interval undefined</div>}
            </div>
          )
        })()}
        {SUMMARY_STATS[currentRole].filter(s => s !== keyStat).map(s => {
          const q = h1Quantiles(data, s)
          const hasBand = isFin(q.q10) && isFin(q.q90)
          return (
            <div key={s} className="card">
              <div className="label">{statLabel(s)}</div>
              <div className="val">{fmtStat(s, q.q50)}</div>
              {hasBand
                ? <div className="range">{fmtRange(s, q.q10, q.q90)}</div>
                : <div className="range muted">interval undefined</div>}
            </div>
          )
        })}
        <div className="card">
          <div className="label">{PT_LABEL[currentRole]}</div>
          <div className="val">{data.pt !== null && data.pt !== undefined ? Math.round(data.pt) : '—'}</div>
          <div className="range">Marcel PT</div>
        </div>
      </div>
      {noH1Band && <div className="muted band-note">{noH1BandNote}</div>}

      <div className="card">
        <h2>{statLabel(keyStat)} — history & projection</h2>
        <FanChart
          history={data.history}
          projections={data.projections[keyStat] ?? []}
          stat={keyStat}
          league={data.league[keyStat] ?? null}
          windowEnd={windowEnd}
          height={280}
        />
        <div className="muted band-note">Bands beyond the first projected season are model-implied, not backtested.</div>
      </div>

      <div className="card">
        <h2>Components</h2>
        <ComponentPanel
          history={data.history}
          projections={data.projections}
          role={currentRole}
          league={data.league}
          windowEnd={windowEnd}
        />
        <div className="muted band-note">Bands beyond the first projected season are model-implied, not backtested.</div>
      </div>

      <div className="card">
        <h2>Why this projection ({statLabel(keyStat)})</h2>
        <Waterfall rows={data.waterfall} stat={keyStat} />
        {(() => {
          const wfFinal = [...data.waterfall]
            .filter(r => r.stat === keyStat && r.value != null && Number.isFinite(r.value as number))
            .sort((a, b) => a.step - b.step)
            .pop()?.value ?? null
          const headline = h1Quantiles(data, keyStat).q50
          if (wfFinal === null || headline === null) return null
          const gap = (headline as number) - (wfFinal as number)
          const sign = gap >= 0 ? '+' : ''
          return (
            <div className="muted band-note">
              This waterfall walks the Bayesian model's own chain and ends at{' '}
              <strong>{fmtStat(keyStat, wfFinal)}</strong>. The headline projection above
              is <strong>{fmtStat(keyStat, headline)}</strong> — Tier 2 didn't clear the
              point-projection gate, so shipped medians are anchored to Marcel (MANUAL §6);
              the gap ({sign}{fmtStat(keyStat, gap)}) is that anchor. Tier 2's spread and
              aging trajectory around the anchor are what the bands and the h=2..4
              projections use.
            </div>
          )
        })()}
      </div>

      <div>
        <AgingOutlook projections={data.projections} aging={data.aging} role={currentRole}
          playingTime={data.playing_time ?? []} />
      </div>

      <div className="card">
        <h2>Year by year</h2>
        <StatTable history={data.history} projections={data.projections} role={currentRole} />
      </div>
    </div>
  )
}

function computeAge(birthISO: string): number | null {
  const d = new Date(birthISO)
  if (Number.isNaN(d.getTime())) return null
  const ref = new Date(`${new Date().getFullYear()}-06-30`)
  let age = ref.getFullYear() - d.getFullYear()
  const before = ref.getMonth() < d.getMonth() || (ref.getMonth() === d.getMonth() && ref.getDate() < d.getDate())
  if (before) age -= 1
  return age
}
