import type { HistoryRow, ProjectionRow, Role } from '../api'
import FanChart from './FanChart'
import { statLabel } from '../format'

const STATS: Record<Role, string[]> = {
  H: ['k_pct', 'bb_pct', 'hr_pct', 'babip'],
  P: ['k_pct', 'bb_pct', 'hr_pct', 'babip'],
}

export default function ComponentPanel({
  history, projections, role, league, windowEnd,
}: {
  history: HistoryRow[]
  projections: Record<string, ProjectionRow[]>
  role: Role
  league: Record<string, number>
  windowEnd: number
}) {
  return (
    <div className="comp-grid">
      {STATS[role].map(stat => (
        <div key={stat} className="card">
          <FanChart
            history={history}
            projections={projections[stat] ?? []}
            stat={stat}
            league={league[stat] ?? null}
            windowEnd={windowEnd}
            height={180}
            title={statLabel(stat)}
          />
        </div>
      ))}
    </div>
  )
}
