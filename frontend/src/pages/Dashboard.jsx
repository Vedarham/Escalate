import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import {
  IconCracks,
  IconKnowledge,
  IconLegal,
  IconPlanning,
  IconSafety,
  IconSiteAssistant,
  IconValuation,
} from '../components/Icons'
import { Badge, Card, PageHeader } from '../components/ui'
import { arr } from '../utils'

export const MODULES = [
  { to: '/safety', key: 'safety', Icon: IconSafety, title: 'Site Safety Monitoring', text: 'Hazards, PPE compliance and corrective actions from jobsite photos.', tag: 'Image' },
  { to: '/cracks', key: 'crack', Icon: IconCracks, title: 'Crack Detection & Analysis', text: 'Crack type, severity, probable causes and repair methods.', tag: 'Image' },
  { to: '/valuation', key: 'valuation', Icon: IconValuation, title: 'Real Estate Valuation', text: 'Market value range, value drivers and rental yield.', tag: 'Data + Image' },
  { to: '/planning', key: 'planning', Icon: IconPlanning, title: 'Project Planning', text: 'Materials, costs, Gantt schedule, critical path and concept design.', tag: 'Data' },
  { to: '/site-assistant', key: 'daily', Icon: IconSiteAssistant, title: 'Daily Site Assistant', text: 'Live weather with go / no-go guidance per activity.', tag: 'Data + Weather' },
  { to: '/knowledge', key: 'chat', Icon: IconKnowledge, title: 'Knowledge Assistant', text: 'Codes, materials, methods and estimation Q&A.', tag: 'Text + Image' },
  { to: '/legal', key: 'legal', Icon: IconLegal, title: 'Land Legal Advisor', text: 'Title, ownership, inheritance and land-purchase risks with cited sources.', tag: 'RAG agent' },
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
          {health?.mode === 'demo' && <span className="small muted">Configure GROQ_API_KEY or HF_TOKEN in Vercel for live AI.</span>}
          {healthErr && <span className="small muted">Connecting to API: check Vercel serverless function logs.</span>}
        </div>
      </Card>

      <div className="modules">
        {MODULES.map((m) => (
          <Link to={m.to} key={m.to} className="module-card">
            <div className="module-icon"><m.Icon size={24} /></div>
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
