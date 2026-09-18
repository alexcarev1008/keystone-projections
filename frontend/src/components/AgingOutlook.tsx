import { Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { AgingPoint, ProjectionRow, Role } from '../api'
import { fmtStat, statLabel } from '../format'

const OUTLOOK_STATS: Record<Role, string[]> = {
  H: ['woba', 'k_pct', 'bb_pct'],
  P: ['fip', 'k_pct', 'bb_pct'],
}
const KEY_STAT: Record<Role, string> = { H: 'woba', P: 'fip' }

export default function AgingOutlook({
  projections, aging, role,
}: {
  projections: Record<string, ProjectionRow[]>
  aging: Record<string, AgingPoint[]>
  role: Role
}) {
  const keyStat = KEY_STAT[role]
  const projRows = projections[keyStat] ?? []
  const curve = (aging[keyStat] ?? []).filter(p => p.value !== null).map(p => ({ age: p.age, value: p.value as number }))
  const playerAges = projRows.map(p => p.age).filter((a): a is number => a !== null && a !== undefined)
  const playerPoints = curve.filter(c => playerAges.includes(c.age))
  const stats = OUTLOOK_STATS[role]

  return (
    <div className="aging-grid">
      <div className="card">
        <h3>Outlook (h = 1…4)</h3>
        <table>
          <thead>
            <tr>
              <th>Season</th>
              <th className="numeric">Age</th>
              {stats.map(s => <th key={s} className="numeric">{statLabel(s)}</th>)}
            </tr>
          </thead>
          <tbody>
            {projRows.map(p => (
              <tr key={p.horizon}>
                <td>{p.season}</td>
                <td className="numeric">{p.age ?? ''}</td>
                {stats.map(s => {
                  const row = (projections[s] ?? []).find(r => r.horizon === p.horizon)
                  return (
                    <td key={s} className="numeric">
                      <div>{fmtStat(s, row?.q50 ?? null)}</div>
                      <div className="range">{fmtStat(s, row?.q10 ?? null)}–{fmtStat(s, row?.q90 ?? null)}</div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3>Typical {statLabel(keyStat)} by age</h3>
        {curve.length === 0 ? <div className="muted">No aging data.</div> : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={curve} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <XAxis dataKey="age" type="number" domain={['dataMin', 'dataMax']} tick={{ fontSize: 11, fill: '#5c677d' }} />
              <YAxis width={52} tick={{ fontSize: 11, fill: '#5c677d' }} tickFormatter={(v: number) => fmtStat(keyStat, v)} domain={['auto', 'auto']} />
              <Tooltip formatter={(v) => fmtStat(keyStat, typeof v === 'number' ? v : Number(v))} />
              <Line type="monotone" dataKey="value" stroke="#1f3a93" strokeWidth={2} dot={false} isAnimationActive={false} />
              {playerPoints.map(pt => (
                <ReferenceDot key={pt.age} x={pt.age} y={pt.value} r={4} fill="#b3261e" stroke="white" strokeWidth={1} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
