import { useEffect, useState } from 'react'
import Search from '../components/Search'
import Leaderboard from '../components/Leaderboard'
import { api, type Meta, type Role } from '../api'

export default function Home() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [role, setRole] = useState<Role>('H')

  useEffect(() => { api.meta().then(r => setMeta(r.meta)).catch(() => setMeta(null)) }, [])

  return (
    <div>
      <div className="hero">
        <h1>KEYSTONE — Bayesian player projections</h1>
        <div className="sub">
          {meta
            ? <>Projections for {meta.projection_season} · data through {meta.data_through}</>
            : 'Loading metadata…'}
        </div>
      </div>

      <Search />

      <div className="card">
        <div className="tabs">
          <button className={role === 'H' ? 'active' : ''} onClick={() => setRole('H')}>Hitters</button>
          <button className={role === 'P' ? 'active' : ''} onClick={() => setRole('P')}>Pitchers</button>
        </div>
        <Leaderboard role={role} />
      </div>
    </div>
  )
}
