import type { WaterfallRow } from '../api'
import { fmtStat, statLabel } from '../format'

// Steps 3 and 4 exist in waterfall.parquet but are intentionally not rendered:
// step 3 ("Statcast contact quality") is NaN for every player — Tier 3 was built and
// backtested but never entered the production projection; step 4 ("Neutral-park
// projection") is byte-identical to step 2 in project.py (`step4 = step2`), so its
// meaning is folded into step 2's label instead of drawing a zero-width duplicate row.
const HIDDEN_STEPS = new Set([3, 4])

const STEP_LABEL: Record<string, string> = {
  '0': '3-year line',
  '1': 'Regression',
  '2': 'Aging — neutral-park projection',
  '5': 'Home park',
}

function rowLabel(r: WaterfallRow): string {
  const base = r.label ?? STEP_LABEL[String(r.step)] ?? `Step ${r.step}`
  return r.step === 2 && r.label ? `${base} — neutral-park projection` : base
}

export default function Waterfall({ rows, stat }: { rows: WaterfallRow[]; stat: string }) {
  const sub = rows
    .filter(r => r.stat === stat && !HIDDEN_STEPS.has(r.step))
    .filter(r => r.value != null && Number.isFinite(r.value))
    .sort((a, b) => a.step - b.step)
  if (sub.length === 0) return <div className="muted">No waterfall data.</div>

  const values = sub.map(r => r.value as number)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = Math.max(hi - lo, 1e-9)
  const width = (v: number) => `${((v - lo) / span) * 100}%`

  const sentences: { label: string; text: string }[] = []
  for (let i = 1; i < sub.length; i++) {
    const delta = (sub[i].value as number) - (sub[i - 1].value as number)
    const sign = delta >= 0 ? '+' : ''
    sentences.push({
      label: rowLabel(sub[i]),
      text: `${sign}${fmtStat(stat, delta)} ${statLabel(stat)}`,
    })
  }

  return (
    <div>
      {sub.map((r, i) => {
        const v = r.value as number
        const isTotal = i === 0 || i === sub.length - 1
        const prev = i > 0 ? (sub[i - 1].value as number) : 0
        const delta = i === 0 ? 0 : v - prev
        const up = delta > 0
        const barW = isTotal ? width(v) : `${(Math.abs(delta) / span) * 100}%`
        const barLeft = isTotal ? '0%' : width(Math.min(v, prev))
        const barColor = isTotal ? 'var(--accent)' : (stat === 'fip' ? (up ? 'var(--accent-2)' : 'var(--accent)') : (up ? 'var(--accent)' : 'var(--accent-2)'))
        return (
          <div key={r.step}>
            <div className="waterfall-row">
              <div className="label">{rowLabel(r)}</div>
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
