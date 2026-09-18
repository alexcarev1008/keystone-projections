export function rate3(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  const s = v.toFixed(3)
  return v >= 0 && v < 1 ? s.replace(/^0\./, '.') : s
}

export function pct(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

export function ratio2(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return v.toFixed(2)
}

export function int0(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—'
  return String(Math.round(v))
}

const RATE_STATS = new Set(['woba', 'avg', 'obp', 'slg', 'iso', 'babip', 'hit_bip'])
const PCT_STATS = new Set(['k_pct', 'bb_pct', 'hr_pct', 'k_minus_bb', 'stage_k', 'stage_bb', 'stage_hbp', 'stage_hr', 'stage_xbh', 'stage_triple'])
const RATIO_STATS = new Set(['fip', 'era'])

export function fmtStat(stat: string, v: number | null | undefined): string {
  if (RATE_STATS.has(stat)) return rate3(v)
  if (PCT_STATS.has(stat)) return pct(v)
  if (RATIO_STATS.has(stat)) return ratio2(v)
  return rate3(v)
}

export function fmtRange(stat: string, lo: number | null | undefined, hi: number | null | undefined): string {
  return `${fmtStat(stat, lo)}–${fmtStat(stat, hi)}`
}

const LABELS: Record<string, string> = {
  woba: 'wOBA',
  avg: 'AVG',
  obp: 'OBP',
  slg: 'SLG',
  iso: 'ISO',
  babip: 'BABIP',
  k_pct: 'K%',
  bb_pct: 'BB%',
  hr_pct: 'HR%',
  k_minus_bb: 'K−BB%',
  fip: 'FIP',
  era: 'ERA',
  hit_bip: 'BABIP',
  hr: 'HR%',
  k: 'K%',
  bb: 'BB%',
  hbp: 'HBP%',
  xbh: 'XBH%',
  triple: '3B%',
  stage_k: 'K%',
  stage_bb: 'BB%',
  stage_hbp: 'HBP%',
  stage_hr: 'HR%',
  stage_xbh: 'XBH%',
  stage_triple: '3B%',
}

export function statLabel(stat: string): string {
  return LABELS[stat] ?? stat
}
