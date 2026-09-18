import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type LeaderboardRow, type Quantiles, type Role } from '../api'
import { fmtStat, fmtRange, statLabel } from '../format'

const KEYS: Record<Role, string[]> = {
  H: ['woba', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
  P: ['fip', 'k_pct', 'bb_pct', 'hr_pct', 'babip'],
}
const DEFAULT_SORT: Record<Role, string> = { H: 'woba', P: 'fip' }
const DEFAULT_ORDER: Record<Role, 'asc' | 'desc'> = { H: 'desc', P: 'asc' }
const DEFAULT_MIN_PT: Record<Role, number> = { H: 300, P: 50 }
const PT_LABEL: Record<Role, string> = { H: 'PA', P: 'IP' }

function q(row: LeaderboardRow, stat: string): Quantiles {
  const v = row[stat] as Quantiles | undefined
  return v ?? { q10: null, q50: null, q90: null }
}

export default function Leaderboard({ role }: { role: Role }) {
  const [sort, setSort] = useState<string>(DEFAULT_SORT[role])
  const [order, setOrder] = useState<'asc' | 'desc'>(DEFAULT_ORDER[role])
  const [rows, setRows] = useState<LeaderboardRow[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    setSort(DEFAULT_SORT[role])
    setOrder(DEFAULT_ORDER[role])
  }, [role])

  useEffect(() => {
    let alive = true
    setLoading(true); setErr(null)
    api.leaderboard(role, sort, order, DEFAULT_MIN_PT[role], 100)
      .then(r => { if (alive) { setRows(r); setLoading(false) } })
      .catch(e => { if (alive) { setErr(String(e)); setLoading(false) } })
    return () => { alive = false }
  }, [role, sort, order])

  const onSort = (s: string) => {
    if (s === sort) setOrder(order === 'asc' ? 'desc' : 'asc')
    else { setSort(s); setOrder(s === 'fip' ? 'asc' : 'desc') }
  }

  const stats = KEYS[role]

  return (
    <div>
      {loading && <div className="loading">Loading…</div>}
      {err && <div className="error">{err}</div>}
      {!loading && !err && (
        <table>
          <thead>
            <tr>
              <th>Player</th>
              <th>Team</th>
              <th className="numeric">Age</th>
              <th className="numeric">{PT_LABEL[role]}</th>
              {stats.map(s => (
                <th key={s} className={`numeric ${s === sort ? 'sorted' : ''}`} onClick={() => onSort(s)}>
                  {statLabel(s)} {s === sort ? (order === 'asc' ? '↑' : '↓') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.mlbam_id}>
                <td><Link to={`/player/${r.mlbam_id}?role=${role}`}>{r.name}</Link></td>
                <td>{r.team ?? ''}</td>
                <td className="numeric">{r.age ?? ''}</td>
                <td className="numeric">{r.pt !== null && r.pt !== undefined ? Math.round(r.pt) : ''}</td>
                {stats.map(s => {
                  const qs = q(r, s)
                  return (
                    <td key={s} className="numeric">
                      <div>{fmtStat(s, qs.q50)}</div>
                      <div className="range">{fmtRange(s, qs.q10, qs.q90)}</div>
                    </td>
                  )
                })}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={4 + stats.length} className="muted">No players.</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
