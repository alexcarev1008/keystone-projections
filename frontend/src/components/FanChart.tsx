import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from 'recharts'
import type { HistoryRow, ProjectionRow } from '../api'
import { fmtStat, statLabel } from '../format'

type Row = {
  season: number
  hist?: number | null
  pa?: number | null
  median?: number | null
  band80?: [number, number] | null
  band50?: [number, number] | null
}

function buildRows(history: HistoryRow[], proj: ProjectionRow[], stat: string): Row[] {
  const bySeason = new Map<number, Row>()
  for (const h of history) {
    const v = (h as unknown as Record<string, number | null>)[stat] ?? null
    const pa = (h.pa ?? h.ip ?? null) as number | null
    bySeason.set(h.season, { season: h.season, hist: v, pa })
  }
  for (const p of proj) {
    const r = bySeason.get(p.season) ?? { season: p.season }
    r.median = p.q50
    r.band80 = p.q10 !== null && p.q90 !== null ? [p.q10, p.q90] : null
    r.band50 = p.q25 !== null && p.q75 !== null ? [p.q25, p.q75] : null
    bySeason.set(p.season, r)
  }
  return Array.from(bySeason.values()).sort((a, b) => a.season - b.season)
}

const paDot = (props: { cx?: number; cy?: number; payload?: Row }) => {
  const { cx, cy, payload } = props
  if (cx === undefined || cy === undefined || payload?.hist === null || payload?.hist === undefined) {
    return <g />
  }
  const pa = payload.pa ?? 0
  const r = Math.max(2.5, Math.min(6, 2.5 + pa / 150))
  return <circle cx={cx} cy={cy} r={r} fill="#14213d" stroke="#fff" strokeWidth={1} />
}

function TipCard({ payload, label, stat }: { payload?: Array<{ name?: string; value?: unknown; payload?: Row }>; label?: number | string; stat: string }) {
  if (!payload || payload.length === 0) return null
  const row = payload[0]?.payload
  if (!row) return null
  return (
    <div style={{ background: 'white', border: '1px solid #e3e6ec', borderRadius: 6, padding: 8, fontSize: 12 }}>
      <div style={{ fontWeight: 600 }}>{label}</div>
      {row.hist !== null && row.hist !== undefined && (
        <div>Actual: {fmtStat(stat, row.hist)}{row.pa ? ` (${Math.round(row.pa)} PA/IP)` : ''}</div>
      )}
      {row.median !== null && row.median !== undefined && (
        <>
          <div>Projected: {fmtStat(stat, row.median)}</div>
          {row.band80 && <div>80%: {fmtStat(stat, row.band80[0])}–{fmtStat(stat, row.band80[1])}</div>}
          {row.band50 && <div>50%: {fmtStat(stat, row.band50[0])}–{fmtStat(stat, row.band50[1])}</div>}
        </>
      )}
    </div>
  )
}

export default function FanChart({
  history, projections, stat, league, windowEnd, height = 240, title,
}: {
  history: HistoryRow[]
  projections: ProjectionRow[]
  stat: string
  league?: number | null
  windowEnd: number
  height?: number
  title?: string
}) {
  const rows = buildRows(history, projections, stat)
  if (rows.length === 0) return <div className="muted">No data.</div>
  return (
    <div>
      {title && <h3>{title}</h3>}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <XAxis dataKey="season" type="number" domain={['dataMin', 'dataMax']} allowDecimals={false} tick={{ fontSize: 11, fill: '#5c677d' }} />
          <YAxis tick={{ fontSize: 11, fill: '#5c677d' }} tickFormatter={(v: number) => fmtStat(stat, v)} width={52} domain={['auto', 'auto']} />
          <Tooltip content={<TipCard stat={stat} />} />
          {league !== null && league !== undefined && (
            <ReferenceLine y={league} stroke="#5c677d" strokeDasharray="4 4" ifOverflow="extendDomain" label={{ value: `Lg ${statLabel(stat)}`, fontSize: 10, fill: '#5c677d', position: 'insideTopRight' }} />
          )}
          <ReferenceLine x={windowEnd + 0.5} stroke="#5c677d" strokeDasharray="2 3" />
          <Area type="monotone" dataKey="band80" stroke="none" fill="var(--band80)" isAnimationActive={false} connectNulls />
          <Area type="monotone" dataKey="band50" stroke="none" fill="var(--band50)" isAnimationActive={false} connectNulls />
          <Line type="monotone" dataKey="median" stroke="#1f3a93" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          <Line type="monotone" dataKey="hist" stroke="#14213d" strokeWidth={1} dot={false} isAnimationActive={false} connectNulls />
          <Scatter dataKey="hist" shape={paDot as unknown as 'circle'} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
