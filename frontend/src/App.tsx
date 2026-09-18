import { NavLink, Route, Routes } from 'react-router-dom'
import Home from './pages/Home'
import Player from './pages/Player'
import Methodology from './pages/Methodology'

export default function App() {
  return (
    <>
      <nav className="nav">
        <div className="container">
          <NavLink to="/" className="nav-title">KEYSTONE</NavLink>
          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Home</NavLink>
            <NavLink to="/methodology" className={({ isActive }) => isActive ? 'active' : ''}>Methodology</NavLink>
          </div>
        </div>
      </nav>
      <main className="container page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/player/:id" element={<Player />} />
          <Route path="/methodology" element={<Methodology />} />
        </Routes>
      </main>
    </>
  )
}
