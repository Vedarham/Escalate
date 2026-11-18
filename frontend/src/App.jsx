import { Component, useState } from 'react'
import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { IconDashboard, IconHistory } from './components/Icons'
import Cracks from './pages/Cracks'
import Dashboard, { MODULES } from './pages/Dashboard'
import History from './pages/History'
import Knowledge from './pages/Knowledge'
import Legal from './pages/Legal'
import Planning from './pages/Planning'
import Safety from './pages/Safety'
import SiteAssistant from './pages/SiteAssistant'
import Valuation from './pages/Valuation'

/** Keeps a rendering bug in one module from blanking the whole app. */
class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  componentDidUpdate(prev) { if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null }) }
  render() {
    if (this.state.error) {
      return (
        <div className="alert alert-error">
          <div><strong>This view failed to render.</strong><p className="small">{String(this.state.error.message || this.state.error)}</p>
            <button className="btn" onClick={() => this.setState({ error: null })}>Try again</button></div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [navOpen, setNavOpen] = useState(false)
  const location = useLocation()
  return (
    <div className="app">
      <aside className={`sidebar ${navOpen ? 'open' : ''}`}>
        <div className="brand">
          <img src="/logo-mark.svg" alt="" className="brand-mark" />
          <div><strong className="wordmark">Escalate</strong><span>Construction Intelligence</span></div>
        </div>
        <nav onClick={() => setNavOpen(false)}>
          <NavLink to="/" end><IconDashboard size={18} /> <span>Dashboard</span></NavLink>
          {MODULES.map((m) => (
            <NavLink key={m.to} to={m.to}><m.Icon size={18} /> <span>{m.title}</span></NavLink>
          ))}
          <NavLink to="/history"><IconHistory size={18} /> <span>History</span></NavLink>
        </nav>
        <div className="sidebar-foot small">© Escalate · AI decision support</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu" onClick={() => setNavOpen((o) => !o)} aria-label="Toggle navigation">☰</button>
          <img src="/logo-mark.svg" alt="" className="topbar-mark" /><span className="topbar-title wordmark">Escalate</span>
        </header>
        <main className="content">
          <ErrorBoundary resetKey={location.pathname}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/safety" element={<Safety />} />
              <Route path="/cracks" element={<Cracks />} />
              <Route path="/valuation" element={<Valuation />} />
              <Route path="/planning" element={<Planning />} />
              <Route path="/site-assistant" element={<SiteAssistant />} />
              <Route path="/knowledge" element={<Knowledge />} />
              <Route path="/legal" element={<Legal />} />
              <Route path="/history" element={<History />} />
              <Route path="*" element={<p className="muted">Page not found.</p>} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
