import { useState } from 'react'
import Dashboard   from './pages/Dashboard.jsx'
import MapPage     from './pages/MapPage.jsx'
import Dispatch    from './pages/Dispatch.jsx'
import Predictions from './pages/Predictions.jsx'
import Chat        from './pages/Chat.jsx'
import Transit     from './pages/Transit.jsx'
import LiveAlerts  from './components/LiveAlerts.jsx'
import { useWebSocket } from './hooks/useWebSocket.js'

// ── SVG nav icons ─────────────────────────────────────────────────────────
const Icon = ({ id, size = 17 }) => {
  const s = { width: size, height: size, display: 'block', flexShrink: 0 }
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: '1.75', strokeLinecap: 'round', strokeLinejoin: 'round' }
  switch (id) {
    case 'dashboard':
      return <svg viewBox="0 0 24 24" style={s} {...p}><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
    case 'map':
      return <svg viewBox="0 0 24 24" style={s} {...p}><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
    case 'transit':
      return <svg viewBox="0 0 24 24" style={s} {...p}><rect x="4" y="3" width="16" height="14" rx="2"/><path d="M8 17l-2 4M16 17l2 4"/><line x1="4" y1="11" x2="20" y2="11"/><circle cx="9" cy="14" r="1.5" fill="currentColor" stroke="none"/><circle cx="15" cy="14" r="1.5" fill="currentColor" stroke="none"/></svg>
    case 'dispatch':
      return <svg viewBox="0 0 24 24" style={s} {...p}><rect x="1" y="3" width="15" height="13" rx="1.5"/><path d="M16 8h4l3 3v5h-7V8z"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/></svg>
    case 'predictions':
      return <svg viewBox="0 0 24 24" style={s} {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
    case 'chat':
      return <svg viewBox="0 0 24 24" style={s} {...p}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    default:
      return null
  }
}

const PAGES = [
  { id: 'dashboard',   label: 'Tableau de bord', sub: 'KPIs & indicateurs'     },
  { id: 'map',         label: 'Carte Live',       sub: 'GPS temps réel'         },
  { id: 'transit',     label: 'Transports',       sub: 'Prochains passages'     },
  { id: 'dispatch',    label: 'Dispatch',         sub: 'Lignes & statuts TC' },
  { id: 'predictions', label: 'ML Prédictions',   sub: 'Analyse des risques'    },
  { id: 'chat',        label: 'Assistant IA',     sub: 'Requêtes en langage naturel' },
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const active = PAGES.find(p => p.id === page)
  const { alerts, connected, dismissAlert } = useWebSocket('/api/v1/ws/live')

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-mark">SL</div>
          <div>
            <div className="logo-title">Smart Logistics</div>
            <div className="logo-sub">Logistique France</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Menu</div>
          {PAGES.map(p => (
            <button
              key={p.id}
              className={`nav-item${page === p.id ? ' active' : ''}`}
              onClick={() => setPage(p.id)}
            >
              <span className="nav-icon"><Icon id={p.id} /></span>
              <span className="nav-label">{p.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`pulse-dot${connected ? '' : ' ws-disconnected'}`} />
            <span>{connected ? 'Flux temps réel actif' : 'Reconnexion…'}</span>
          </div>
          <div className="sidebar-year">v1.0 · {new Date().getFullYear()}</div>
        </div>
      </aside>

      {/* ── Live alert toasts ── */}
      <LiveAlerts alerts={alerts} onDismiss={dismissAlert} />

      {/* ── Main content ── */}
      <div className={`content${page === 'map' ? ' map-container' : ''}`}>
        {page !== 'map' && (
          <div className="content-header">
            <div className="content-header-icon"><Icon id={page} size={20} /></div>
            <div>
              <h2>{active?.label}</h2>
              {active?.sub && <div className="sub">{active.sub}</div>}
            </div>
          </div>
        )}
        {page === 'dashboard'   && <Dashboard />}
        {page === 'map'         && <MapPage />}
        {page === 'transit'     && <Transit />}
        {page === 'dispatch'    && <Dispatch />}
        {page === 'predictions' && <Predictions />}
        {page === 'chat'        && <Chat />}
      </div>
    </div>
  )
}
