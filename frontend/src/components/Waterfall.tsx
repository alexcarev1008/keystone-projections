import type { WaterfallRow } from '../api'
import { fmtStat, statLabel } from '../format'

const STEP_LABEL: Record<string, string> = {
  '0': '3-year line',
  '1': 'Regression',
  '2': 'Aging',
  '3': 'Statcast',
  '4': 'Neutral park',
  '5': 'Home park',
}

export default function Waterfall({ rows, stat }: { rows: WaterfallRow[]; stat: string }) {
  const sub = rows.filter(r => r.stat === stat).sort((a, b) => a.step - b.step)
  if (sub.length === 0) return <div className="muted">No waterfall data.</div>

  const values = sub.map(r => r.value ?? 0)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = Math.max(hi - lo, 1e-9)
  const width = (v: number) => `${((v - lo) / span) * 100}%`

  const sentences: { label: string; text: string }[] = []
  for (let i = 1; i < sub.length; i++) {
    const prev = sub[i - 1].value ?? 0
    const cur = sub[i].value ?? 0
    const delta = cur - prev
    const sign = delta >= 0 ? '+' : ''
    sentences.push({
      label: sub[i].label ?? STEP_LABEL[String(sub[i].step)] ?? `Step ${sub[i].step}`,
      text: `${sign}${fmtStat(stat, delta)} ${statLabel(stat)}`,
    })
  }

  return (
    <div>
      {sub.map((r, i) => {
        const v = r.value ?? 0
        const isTotal = i === 0 || i === sub.length - 1
        const prev = i > 0 ? (sub[i - 1].value ?? 0) : 0
        const delta = i === 0 ? 0 : v - prev
        const up = delta > 0
        const barW = isTotal ? width(v) : `${(Math.abs(delta) / span) * 100}%`
        const barLeft = isTotal ? '0%' : width(Math.min(v, prev))
        const barColor = isTotal ? 'var(--accent)' : (stat === 'fip' ? (up ? 'var(--accent-2)' : 'var(--accent)') : (up ? 'var(--accent)' : 'var(--accent-2)'))
        return (
          <div key={i}>
            <div className="waterfall-row">
              <div className="label">{r.label ?? STEP_LABEL[String(r.step)] ?? `Step ${r.step}`}</div>
              <div className="waterfall-bar">
                <div style={{ position: 'absolute', left: barLeft, width: barW, top: 0, bottom: 0, background: barColor, borderRadius: 3 }} />
              </div>
              <div className="val">{fmtStat(stat, v)}</div>
            </div>
            {i > 0 && i < sub.length - 1 && (
              <div className="waterfall-sentence">
                {sentences[i - 1].label}: {sentences[i - 1].text}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
