export type Role = 'H' | 'P'

export type SearchHit = {
  mlbam_id: number
  name: string
  roles: string
  primary_pos: string | null
  last_team_abbr: string | null
}

export type Quantiles = { q10: number | null; q50: number | null; q90: number | null }

export type LeaderboardRow = {
  mlbam_id: number
  name: string
  team: string | null
  age: number | null
  pt: number | null
} & Record<string, unknown>

export type Bio = {
  mlbam_id: number
  name: string
  roles: string
  primary_pos: string | null
  bats: string | null
  throws: string | null
  birth_date: string | null
  last_team_abbr: string | null
  last_season: number | null
}

export type HistoryRow = {
  season: number
  team_abbr: string | null
  age: number | null
  pa: number | null
  ip?: number | null
  k_pct: number | null
  bb_pct: number | null
  hr_pct: number | null
  babip: number | null
  avg?: number | null
  obp?: number | null
  slg?: number | null
  iso?: number | null
  woba?: number | null
  k_minus_bb?: number | null
  fip?: number | null
  era?: number | null
  [k: string]: unknown
}

export type ProjectionRow = {
  season: number
  horizon: number
  age: number | null
  q10: number | null
  q25: number | null
  q50: number | null
  q75: number | null
  q90: number | null
  mean: number | null
  tier: string | null
}

// M3 playing-time outlook (hurdle model), one per horizon. Null = outside the PT population.
export type PlayingTimeRow = {
  season: number
  horizon: number
  age: number | null
  p_play: number | null
  pt_expected: number | null
  p_regular: number | null
}

export type WaterfallRow = {
  stat: string
  step: number
  label: string
  value: number | null
}

export type AgingPoint = { age: number; value: number | null }

export type PlayerResponse = {
  bio: Bio
  role: Role
  history: HistoryRow[]
  projections: Record<string, ProjectionRow[]>
  pt: number | null
  playing_time?: PlayingTimeRow[]
  waterfall: WaterfallRow[]
  aging: Record<string, AgingPoint[]>
  league: Record<string, number>
}

export type Meta = {
  generated_at?: string
  data_through?: string
  window_end?: number
  projection_season?: number
  production_tier?: { H?: string; P?: string }
  model_config?: { obs_noise?: boolean; env_mode?: string }
  max_rhat?: number
  total_divergences?: number
  stages?: Record<string, Record<string, unknown>>
  park_top?: { role: string; stage: string; top: Array<{ venue_id: number; name: string; phi: number }>; bottom: Array<{ venue_id: number; name: string; phi: number }> }[]
  [k: string]: unknown
}

export type BacktestRow = {
  target: number
  role: Role
  tier: string
  stat: string
  n: number | null
  rmse: number | null
  mae: number | null
  cov50: number | null
  cov80: number | null
}

export type Backtest = {
  generated_at?: string
  targets?: number[]
  holdout_target?: number | null
  rows: BacktestRow[]
  gates: Record<string, Record<string, boolean | null>>
  production_tier: { H: string; P: string }
} | null

async function j<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} for ${url}`)
  return r.json() as Promise<T>
}

export const api = {
  search: (q: string, limit = 10) =>
    j<SearchHit[]>(`/api/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  leaderboard: (role: Role, sort?: string, order?: 'asc' | 'desc', min_pt?: number, limit = 100) => {
    const p = new URLSearchParams({ role, limit: String(limit) })
    if (sort) p.set('sort', sort)
    if (order) p.set('order', order)
    if (min_pt !== undefined) p.set('min_pt', String(min_pt))
    return j<LeaderboardRow[]>(`/api/leaderboard?${p.toString()}`)
  },
  player: (id: number | string, role?: Role) => {
    const p = new URLSearchParams()
    if (role) p.set('role', role)
    const qs = p.toString()
    return j<PlayerResponse>(`/api/players/${id}${qs ? `?${qs}` : ''}`)
  },
  meta: () => j<{ meta: Meta; backtest: Backtest }>('/api/meta'),
}
