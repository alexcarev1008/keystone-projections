import type { HistoryRow, ProjectionRow, Role } from '../api'
import { fmtStat, int0, statLabel } from '../format'

const STATS: Record<Role, string[]> = {
  H: ['woba', 'k_pct', 'bb_pct', 'hr_pct', 'babip', 'avg', 'obp', 'slg', 'iso'],
  P: ['fip', 'k_pct', 'bb_pct', 'hr_pct', 'babip', 'k_minus_bb', 'era'],
}
const PT_LABEL: Record<Role, string> = { H: 'PA', P: 'IP' }

function pickPT(row: HistoryRow, role: Role): number | null {
  const v = role === 'P' ? (row.ip ?? row.pa) : row.pa
  return v === null || v === undefined ? null : Number(v)
}

export default function StatTable({
  history, projections, role,
}: {
  history: HistoryRow[]
  projections: Record<string, ProjectionRow[]>
  role: Role
}) {
  const stats = STATS[role]
  const projRows: Array<{ season: number; age: number | null; horizon: number; vals: Record<string, number | null> }> = []
  const horizons = new Set<number>()
  for (const list of Object.values(projections)) for (const r of list) horizons.add(r.horizon)
  const sortedHorizons = Array.from(horizons).sort((a, b) => a - b)
  for (const h of sortedHorizons) {
    const first = (projections[stats[0]] ?? []).find(r => r.horizon === h)
    const vals: Record<string, number | null> = {}
    for (const s of stats) {
      const row = (projections[s] ?? []).find(r => r.horizon === h)
      vals[s] = row?.q50 ?? null
    }
    projRows.push({ season: first?.season ?? 0, age: first?.age ?? null, horizon: h, vals })
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Season</th>
          <th>Team</th>
          <th className="numeric">Age</th>
          <th className="numeric">{PT_LABEL[role]}</th>
          {stats.map(s => <th key={s} className="numeric">{statLabel(s)}</th>)}
        </tr>
      </thead>
      <tbody>
        {history.map(h => (
          <tr key={`h-${h.season}`}>
            <td>{h.season}</td>
            <td>{h.team_abbr ?? ''}</td>
            <td className="numeric">{h.age ?? ''}</td>
            <td className="numeric">{int0(pickPT(h, role))}</td>
            {stats.map(s => (
              <td key={s} className="numeric">{fmtStat(s, (h as unknown as Record<string, number | null>)[s] ?? null)}</td>
            ))}
          </tr>
        ))}
        {projRows.map(p => (
          <tr key={`p-${p.horizon}`} className="projected">
            <td>{p.season}</td>
            <td>proj</td>
            <td className="numeric">{p.age ?? ''}</td>
            <td className="numeric"></td>
            {stats.map(s => <td key={s} className="numeric">{fmtStat(s, p.vals[s])}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
