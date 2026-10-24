import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Badge, Card, PageHeader } from '../components/ui'
import { arr } from '../utils'

export const MODULES = [
  { to: '/safety', key: 'safety', icon: '🦺', title: 'Site Safety Monitoring', text: 'Hazards, PPE compliance and corrective actions from jobsite photos.', tag: 'Image' },
  { to: '/cracks', key: 'crack', icon: '🧱', title: 'Crack Detection & Analysis', text: 'Crack type, severity, probable causes and repair methods.', tag: 'Image' },
  { to: '/valuation', key: 'valuation', icon: '🏠', title: 'Real Estate Valuation', text: 'Market value range, value drivers and rental yield.', tag: 'Data + Image' },
  { to: '/planning', key: 'planning', icon: '📐', title: 'Project Planning', text: 'Materials, costs, Gantt schedule, critical path and concept design.', tag: 'Data' },
  { to: '/site-assistant', key: 'daily', icon: '🌦', title: 'Daily Site Assistant', text: 'Live weather with go / no-go guidance per activity.', tag: 'Data + Weather' },
  { to: '/knowledge', key: 'chat', icon: '💬', title: 'Knowledge Assistant', text: 'Codes, materials, methods and estimation Q&A.', tag: 'Text + Image' },
  { to: '/legal', key: 'legal', icon: '⚖️', title: 'Land Legal Advisor', text: 'Title, ownership, inheritance and land-purchase risks with cited sources.', tag: 'RAG agent' },
]

export default function Dashboard() {
  const [health, setHealth] = useState(null)
  const [healthErr, setHealthErr] = useState(null)
  const [history, setHistory] = useState(null)

  useEffect(() => {
    api.health().then((r) => setHealth(r.data)).catch(setHealthErr)
    api.history().then((r) => setHistory(r.data)).catch(() => setHistory({ items: [], counts: {} }))
  }, [])

  const counts = history?.counts || {}
  return (
    <>
      <PageHeader icon={<img src="/logo-mark.svg" alt="" className="page-logo" />} title="Escalate Dashboard"
        subtitle="Multimodal AI decision support across planning, execution and monitoring." />

      <Card>
        <div className="row between wrap">
          <div className="row gap wrap">
            <strong>AI engine</strong>
            {healthErr && <Badge value="critical" text="Backend offline" />}
            {health && <Badge value={health.mode === 'live' ? 'go' : 'caution'} text={health.mode === 'live' ? 'Live' : 'Demo mode'} />}
            {health?.providers?.map((p, i) => (
              <span key={p.name} className="small muted">{i === 0 ? 'Primary' : 'Fallback'}: <strong>{p.name}</strong> ({p.vision_model})</span>
            ))}
          </div>
          {health?.mode === 'demo' && <span className="small muted">Add GROQ_API_KEY or HF_TOKEN to backend/.env for live AI.</span>}
          {healthErr && <span className="small muted">Start the backend: <code>uvicorn app.main:app --reload</code></span>}
        </div>
      </Card>

      <div className="modules">
        {MODULES.map((m) => (
          <Link to={m.to} key={m.to} className="module-card">
            <div className="module-icon">{m.icon}</div>
            <div className="grow">
              <div className="row between"><h3>{m.title}</h3><span className="tag">{m.tag}</span></div>
              <p>{m.text}</p>
              <span className="small muted">{counts[m.key] || 0} analyses run</span>
            </div>
          </Link>
        ))}
      </div>

      <Card title="Recent activity" actions={<Link to="/history" className="link-btn">View all</Link>}>
        {!history && <p className="muted">Loading…</p>}
        {history && arr(history.items).length === 0 && <p className="muted">No analyses yet. Pick a module above to get started.</p>}
        <ul className="activity">
          {arr(history?.items).slice(0, 6).map((i) => (
            <li key={i.id}>
              <span className="tag">{i.module}</span> {i.title}
              <span className="small muted"> · {new Date(i.created_at).toLocaleString()} · {i.mode}</span>
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
