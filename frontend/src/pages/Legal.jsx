import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { IconLegal } from '../components/Icons'
import ImageUpload from '../components/ImageUpload'
import { Badge, Card, Confidence, ErrorBanner, Field, List, Markdown, PageHeader } from '../components/ui'
import { arr, label, num } from '../utils'

const STATES = [
  ['', 'Not specified'], ['maharashtra', 'Maharashtra'], ['karnataka', 'Karnataka'], ['tamil-nadu', 'Tamil Nadu'],
  ['telangana', 'Telangana'], ['andhra-pradesh', 'Andhra Pradesh'], ['uttar-pradesh', 'Uttar Pradesh'],
  ['delhi', 'Delhi'], ['gujarat', 'Gujarat'], ['madhya-pradesh', 'Madhya Pradesh'], ['other', 'Other state'],
]
const PROPERTY = ['unknown', 'agricultural_land', 'residential_plot', 'apartment', 'house', 'commercial', 'industrial']
const BUYER = ['resident_indian', 'nri', 'oci', 'foreign_national', 'company', 'unknown']
const SUGGESTIONS = [
  'The seller has only a GPA from the owner. Is it safe to buy?',
  'I am not a farmer. Can I buy agricultural land in Maharashtra?',
  'My grandfather died without a will and my uncle sold the house. Does my mother have a right?',
  'What documents should I verify before buying a plot?',
  'Someone has been occupying the plot I want to buy for 15 years.',
  'The land has a bank loan. How do I pay safely?',
]

export default function Legal() {
  const [profile, setProfile] = useState({ jurisdiction: '', property_type: 'unknown', buyer_profile: 'resident_indian' })
  const [image, setImage] = useState(null)
  const [messages, setMessages] = useState([]) // {role, content, data?, meta?, image?}
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [kb, setKb] = useState(null)
  const endRef = useRef(null)
  const set = (k) => (e) => setProfile({ ...profile, [k]: e.target.value })

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])
  useEffect(() => {
    api.legalKb().then((r) => setKb(r.data)).catch(() => setKb({ articles: [] }))
  }, [])

  const ask = async (text) => {
    const q = (text ?? input).trim()
    if (!q || loading) return
    const next = [...messages, { role: 'user', content: q, image: image ? URL.createObjectURL(image) : null }]
    setMessages(next)
    setInput('')
    setError(null)
    setLoading(true)
    try {
      // assistant turns are sent back as their short summaries to keep the context small
      const history = next.map((m) => ({ role: m.role, content: (m.data?.summary || m.content).slice(0, 4000) })).slice(-8)
      const res = await api.legal({ messages: history, ...profile }, image)
      setMessages([...next, { role: 'assistant', content: res.data.summary, data: res.data, meta: res.meta }])
      setImage(null)
    } catch (e) {
      setError(e)
      setMessages(messages)
      setInput(q)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader icon={<IconLegal size={28} color="var(--accent)" />} title="Land Purchase Legal Advisor"
        subtitle="Ask about title, ownership, inheritance, agricultural restrictions, fraud and due diligence. Answers are grounded in a cited land-law knowledge base." />
      <div className="layout-2">
        <div className="stack">
          <Card title="Your situation">
            <div className="form">
              <Field label="State where the property is">
                <select value={profile.jurisdiction} onChange={set('jurisdiction')}>
                  {STATES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
              <div className="grid-2">
                <Field label="Property type">
                  <select value={profile.property_type} onChange={set('property_type')}>
                    {PROPERTY.map((p) => <option key={p} value={p}>{p === 'unknown' ? 'Not specified' : label(p)}</option>)}
                  </select>
                </Field>
                <Field label="Buyer">
                  <select value={profile.buyer_profile} onChange={set('buyer_profile')}>
                    {BUYER.map((b) => <option key={b} value={b}>{b === 'nri' ? 'NRI' : b === 'oci' ? 'OCI' : label(b)}</option>)}
                  </select>
                </Field>
              </div>
              <ImageUpload file={image} onChange={setImage} label="Document photo (7/12, sale deed, EC…)" optional />
              <p className="small muted">The photo is sent with your next question and reviewed by the vision model.</p>
            </div>
          </Card>
          <Card title={`Knowledge base${kb ? ` · ${arr(kb.articles).length} articles` : ''}`}>
            <details>
              <summary className="small">Browse topics covered</summary>
              <ul className="kb-list">
                {arr(kb?.articles).map((a) => (
                  <li key={a.id}><span className="tag">{a.id}</span> {a.title}</li>
                ))}
              </ul>
            </details>
            <p className="small muted">Indian land &amp; property law: Transfer of Property, Registration, succession, RERA, FEMA,
              land-revenue records for 9 states and common frauds.</p>
          </Card>
        </div>

        <div className="chat legal-chat">
          <div className="chat-log">
            {messages.length === 0 && (
              <div className="chat-empty">
                <p className="muted">Describe your situation or pick a common question:</p>
                <div className="chips">
                  {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              m.role === 'user'
                ? <div key={i} className="bubble user">{m.image && <img src={m.image} alt="document" className="bubble-img" />}<p>{m.content}</p></div>
                : <Advice key={i} data={m.data} meta={m.meta} onAsk={setInput} />
            ))}
            {loading && <div className="bubble assistant"><span className="spinner" /> Researching the knowledge base and drafting advice…</div>}
            <div ref={endRef} />
          </div>
          <ErrorBanner error={error} onClose={() => setError(null)} />
          <form className="chat-input" onSubmit={(e) => { e.preventDefault(); ask() }}>
            <textarea rows={2} value={input} maxLength={8000} placeholder="e.g. The 7/12 shows a different name than the seller. What should I do?"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() } }} />
            <button className="btn" disabled={loading || !input.trim()}>Ask</button>
            {messages.length > 0 && <button type="button" className="link-btn" onClick={() => setMessages([])}>New</button>}
          </form>
        </div>
      </div>
    </>
  )
}

function Advice({ data, meta, onAsk }) {
  const d = data || {}
  const [open, setOpen] = useState(null)
  const sources = arr(d.sources)
  const toggle = (id) => setOpen((cur) => (cur === id ? null : id))
  const openSource = sources.find((s) => s.id === open)

  if (d.in_scope === false) {
    return (
      <div className="bubble assistant advice">
        <Badge value="caution" text="Outside land & property law" />
        <p>{d.summary}</p>
        <p className="small muted">Try asking about title, ownership, inheritance, registration or land restrictions.</p>
      </div>
    )
  }
  return (
    <div className="bubble assistant advice">
      <div className="row between wrap">
        <div className="row gap"><span className="muted small">Buyer risk</span><Badge value={d.risk_level} /></div>
        <Confidence value={d.confidence} />
      </div>
      <div className="advice-summary"><Markdown text={d.summary} onCite={toggle} /></div>
      <Markdown text={d.detailed_answer} onCite={toggle} />
      {openSource && <SourceCard s={openSource} onClose={() => setOpen(null)} />}

      {arr(d.red_flags).length > 0 && (
        <section className="advice-sec">
          <h4>Red flags</h4>
          {d.red_flags.map((f, i) => (
            <div className="flag" key={i}>
              <div className="row between"><strong>{f.issue}</strong><Badge value={f.severity} /></div>
              <p className="small">{f.why_it_matters}</p>
            </div>
          ))}
        </section>
      )}
      {arr(d.documents_to_verify).length > 0 && (
        <section className="advice-sec">
          <h4>Documents to verify</h4>
          <table className="table">
            <thead><tr><th>Document</th><th>Why</th><th>Where to get it</th></tr></thead>
            <tbody>{d.documents_to_verify.map((x, i) => <tr key={i}><td>{x.document}</td><td>{x.purpose}</td><td>{x.where_to_get}</td></tr>)}</tbody>
          </table>
        </section>
      )}
      {arr(d.next_steps).length > 0 && (
        <section className="advice-sec"><h4>Next steps</h4><ol className="list">{d.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol></section>
      )}
      {arr(d.clarifying_questions).length > 0 && (
        <section className="advice-sec">
          <h4>To refine the answer, tell me:</h4>
          <div className="chips">{d.clarifying_questions.map((q, i) => <button key={i} type="button" className="chip small" onClick={() => onAsk(q + ' ')}>{q}</button>)}</div>
        </section>
      )}
      {arr(d.applicable_laws).length > 0 && (
        <div className="refs">{d.applicable_laws.map((l, i) => <span className="tag" key={i}>📘 {l}</span>)}</div>
      )}
      {d.when_to_consult_lawyer && <div className="alert alert-warn small">👩‍⚖️ {d.when_to_consult_lawyer}</div>}

      <details className="advice-sec">
        <summary>Sources searched ({sources.length}) · cited {arr(d.citations).length}</summary>
        {sources.map((s) => (
          <div key={s.id} className={`source ${s.cited ? 'cited' : ''}`}>
            <div className="row between"><button type="button" className="cite" onClick={() => toggle(s.id)}>{s.id}</button>
              <span className="small muted">{s.cited ? 'cited' : 'retrieved'} · score {num(s.score).toFixed(1)}</span></div>
            <strong className="small">{s.title}</strong>
          </div>
        ))}
        {d.plan && <p className="small muted">Agent plan: {arr(d.plan.issue_categories).join(', ') || '—'} · queries: {arr(d.plan.search_queries).join(' | ')}</p>}
      </details>
      <p className="small muted disclaimer">{d.disclaimer}</p>
      <div className="small muted bubble-meta">{meta?.mode === 'demo' ? 'Demo mode (retrieval is live)' : meta?.model} · {(num(meta?.latency_ms) / 1000).toFixed(1)}s
        {arr(meta?.warnings).length > 0 && ` · ⚠ ${meta.warnings.join(' ')}`}</div>
    </div>
  )
}

function SourceCard({ s, onClose }) {
  const [full, setFull] = useState(null)
  useEffect(() => {
    let alive = true
    api.legalArticle(s.id).then((r) => alive && setFull(r.data)).catch(() => {})
    return () => { alive = false }
  }, [s.id])
  return (
    <div className="source-card">
      <div className="row between"><strong>{s.id} · {s.title}</strong><button type="button" className="icon-btn" onClick={onClose} aria-label="Close">×</button></div>
      <p className="small muted">📘 {s.sources}</p>
      <Markdown text={full?.body || s.excerpt} />
    </div>
  )
}
