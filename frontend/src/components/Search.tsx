import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type SearchHit } from '../api'

export default function Search() {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [open, setOpen] = useState(false)
  const nav = useNavigate()
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!q.trim()) { setHits([]); return }
    const h = setTimeout(() => {
      api.search(q, 10).then(setHits).catch(() => setHits([]))
    }, 250)
    return () => clearTimeout(h)
  }, [q])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const go = (h: SearchHit) => {
    const role = h.roles.includes('H') ? 'H' : 'P'
    nav(`/player/${h.mlbam_id}?role=${role}`)
    setOpen(false)
    setQ('')
  }

  return (
    <div className="search" ref={boxRef}>
      <input
        placeholder="Search players (name, e.g. Soto, Judge, Ohtani)…"
        value={q}
        onChange={e => { setQ(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => { if (e.key === 'Enter' && hits[0]) go(hits[0]) }}
      />
      {open && hits.length > 0 && (
        <div className="dropdown">
          {hits.map(h => (
            <a
              key={`${h.mlbam_id}-${h.roles}`}
              href={`/player/${h.mlbam_id}`}
              onClick={e => { e.preventDefault(); go(h) }}
            >
              <span>{h.name}</span>
              <span className="small">{h.last_team_abbr ?? ''} · {h.primary_pos ?? ''} · {h.roles}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
