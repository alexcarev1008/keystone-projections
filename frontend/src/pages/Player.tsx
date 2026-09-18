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
              <div className="range">80%: {fmtRange(keyStat, q.q10, q.q90)}</div>
            </div>
          )
        })()}
        {SUMMARY_STATS[currentRole].filter(s => s !== keyStat).map(s => {
          const q = h1Quantiles(data, s)
          return (
            <div key={s} className="card">
              <div className="label">{statLabel(s)}</div>
              <div className="val">{fmtStat(s, q.q50)}</div>
              <div className="range">{fmtRange(s, q.q10, q.q90)}</div>
            </div>
          )
        })}
        <div className="card">
          <div className="label">{PT_LABEL[currentRole]}</div>
          <div className="val">{data.pt !== null && data.pt !== undefined ? Math.round(data.pt) : '—'}</div>
          <div className="range">Marcel PT</div>
        </div>
      </div>

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
      </div>

      <div className="card">
        <h2>Why this projection ({statLabel(keyStat)})</h2>
        <Waterfall rows={data.waterfall} stat={keyStat} />
      </div>

      <div>
        <AgingOutlook projections={data.projections} aging={data.aging} role={currentRole} />
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
