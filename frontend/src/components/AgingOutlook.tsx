import { Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { AgingPoint, PlayingTimeRow, ProjectionRow, Role } from '../api'
import { fmtStat, int0, statLabel } from '../format'

const OUTLOOK_STATS: Record<Role, string[]> = {
  H: ['woba', 'k_pct', 'bb_pct'],
  P: ['fip', 'k_pct', 'bb_pct'],
}
const KEY_STAT: Record<Role, string> = { H: 'woba', P: 'fip' }
const PT_LABEL: Record<Role, string> = { H: 'PA', P: 'IP' }
// Counting stats = projected rate (posterior mean) × playing time. Pitchers show IP only:
// the rates are per batter faced and there is no per-player BF/IP conversion in the artifacts.
const COUNT_STATS: Record<Role, Array<{ label: string; rate: string }>> = {
  H: [{ label: 'HR', rate: 'hr_pct' }, { label: 'BB', rate: 'bb_pct' }, { label: 'K', rate: 'k_pct' }],
  P: [],
}
// Playing time is shown for h1 only. The hurdle model is backtested at h1 only (make pt-backtest),
// and at h2+ it feeds its own simulated healthy seasons back in as the recent-PT feature, so expected
// PT rises with age for players whose recent PT was injury-depressed (Judge: 545/579/620/646 PA at
// ages 35-38 while his wOBA declines .419 to .369). We do not display a number we have not validated.
const PT_MAX_HORIZON = 1

const isNum = (v: number | null | undefined): v is number => v !== null && v !== undefined && Number.isFinite(v)
const pctInt = (v: number | null | undefined) => (isNum(v) ? `${Math.round(v * 100)}%` : '—')

export default function AgingOutlook({
  projections, aging, role, playingTime = [],
}: {
  projections: Record<string, ProjectionRow[]>
  aging: Record<string, AgingPoint[]>
  role: Role
  playingTime?: PlayingTimeRow[]
}) {
  const keyStat = KEY_STAT[role]
  const projRows = projections[keyStat] ?? []
  const curve = (aging[keyStat] ?? []).filter(p => p.value !== null).map(p => ({ age: p.age, value: p.value as number }))
  const playerAges = projRows.map(p => p.age).filter((a): a is number => a !== null && a !== undefined)
  const playerPoints = curve.filter(c => playerAges.includes(c.age))
  const stats = OUTLOOK_STATS[role]
  const counts = COUNT_STATS[role]
  const ptBy = new Map(playingTime.map(r => [r.horizon, r]))
  const hasPT = playingTime.some(r => isNum(r.pt_expected))
  const h1 = ptBy.get(1)
  const rateOf = (stat: string, h: number) => (projections[stat] ?? []).find(r => r.horizon === h)?.mean ?? null
  const nCols = 3 + 1 + counts.length + stats.length

  return (
    <div className="aging-grid">
      <div className="card">
        <h3>Outlook (h = 1…4)</h3>
        {hasPT && h1 && isNum(h1.p_regular) && (
          <div className="outlook-chip">
            Chance still an MLB regular in {h1.season}{' '}
            <span className="muted">(≥ {role === 'H' ? '300 PA' : '100 IP'})</span> —{' '}
            <strong>{pctInt(h1.p_regular)}</strong>
          </div>
        )}
        <div className="table-scroll">
          <table className="outlook-table">
            <thead>
              <tr>
                <th>Season</th>
                <th className="numeric">Age</th>
                <th></th>
                <th className="numeric">{PT_LABEL[role]}</th>
                {counts.map(c => <th key={c.label} className="numeric">{c.label}</th>)}
                {stats.map(s => <th key={s} className="numeric">{statLabel(s)}</th>)}
              </tr>
            </thead>
            <tbody>
              {projRows.map(p => {
                const pt = ptBy.get(p.horizon)
                const exp = pt && isNum(pt.pt_expected) ? pt.pt_expected : null
                const cond = exp !== null && pt && isNum(pt.p_play) && pt.p_play > 0 ? exp / pt.p_play : null
                const ptShown = hasPT && p.horizon <= PT_MAX_HORIZON
                const lines: Array<{ key: string; label: string; pt: number | null }> = ptShown
                  ? [{ key: 'if', label: 'If he plays', pt: cond }, { key: 'exp', label: 'Expected', pt: exp }]
                  : [{ key: 'if', label: '', pt: null }]
                return lines.map((line, li) => (
                  <tr key={`${p.horizon}-${line.key}`} className={li === 0 ? 'outlook-first' : 'outlook-second'}>
                    {li === 0 && <td rowSpan={lines.length}>{p.season}</td>}
                    {li === 0 && <td rowSpan={lines.length} className="numeric">{p.age ?? ''}</td>}
                    {hasPT && !ptShown ? (
                      <td colSpan={2 + counts.length} className="muted outlook-note">
                        rates only — playing time projected one year ahead
                      </td>
                    ) : (
                      <>
                        <td className="outlook-line">{line.label}</td>
                        <td className="numeric">{int0(line.pt)}</td>
                        {counts.map(c => {
                          const r = rateOf(c.rate, p.horizon)
                          return <td key={c.label} className="numeric">{isNum(r) && isNum(line.pt) ? int0(r * line.pt) : '—'}</td>
                        })}
                      </>
                    )}
                    {line.key === 'exp' ? (
                      <td colSpan={stats.length} className="numeric muted outlook-note">
                        rates as above · {pctInt(pt?.p_play)} chance he plays
                      </td>
                    ) : stats.map(s => {
                      const row = (projections[s] ?? []).find(r => r.horizon === p.horizon)
                      return (
                        <td key={s} className="numeric">
                          <div>{fmtStat(s, row?.q50 ?? null)}</div>
                          <div className="range">
                            {fmtStat(s, row?.q10 ?? null)}–{fmtStat(s, row?.q90 ?? null)}{p.horizon > 1 ? '†' : ''}
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))
              })}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={nCols} className="muted outlook-foot">
                  {hasPT ? (
                    <>
                      <strong>If he plays</strong>: {PT_LABEL[role]} given any MLB time, with the conditional rate projections.{' '}
                      <strong>Expected</strong>: includes the chance of no MLB time (playing-time hurdle model);
                      counting stats = projected rate × {PT_LABEL[role]}. Playing time is shown for year 1
                      only; it is not backtested beyond that.{' '}
                    </>
                  ) : (
                    <>No playing-time outlook for this player (no MLB time in the last two seasons); rates are conditional on playing.{' '}</>
                  )}
                  † Beyond year 1, intervals are model-implied, not backtested.
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
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
