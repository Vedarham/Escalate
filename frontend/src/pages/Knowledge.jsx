import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import ImageUpload from '../components/ImageUpload'
import { Badge, ErrorBanner, Markdown, PageHeader } from '../components/ui'
import { arr, num } from '../utils'

const SUGGESTIONS = [
  'What is the minimum curing period for M25 concrete in hot weather?',
  'Nominal cover for columns and footings as per IS 456?',
  'How do I calculate bricks needed for a 230 mm wall?',
  'Difference between shrinkage and settlement cracks?',
]

export default function Knowledge() {
  const [messages, setMessages] = useState([]) // {role, content, data?, meta?}
  const [input, setInput] = useState('')
  const [image, setImage] = useState(null)
  const [showUpload, setShowUpload] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || loading) return
    const next = [...messages, { role: 'user', content: q, image: image ? URL.createObjectURL(image) : null }]
    setMessages(next)
    setInput('')
    setError(null)
    setLoading(true)
    try {
      const history = next.map((m) => ({ role: m.role, content: m.content.slice(0, 8000) })).slice(-20)
      const res = await api.chat(history, image)
      setMessages([...next, { role: 'assistant', content: res.data.answer || '(no answer)', data: res.data, meta: res.meta }])
      setImage(null)
      setShowUpload(false)
    } catch (e) {
      setError(e)
      setMessages(messages) // roll back the unanswered question
      setInput(q)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader icon="💬" title="Construction Knowledge Assistant"
        subtitle="Ask about codes, materials, methods, estimation and safety — attach a photo if useful." />
      <div className="chat">
        <div className="chat-log">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p className="muted">Try one of these:</p>
              <div className="chips">
                {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.image && <img src={m.image} alt="attached" className="bubble-img" />}
              {m.role === 'user' ? <p>{m.content}</p> : <Answer m={m} onAsk={send} />}
            </div>
          ))}
          {loading && <div className="bubble assistant"><span className="spinner" /> Thinking…</div>}
          <div ref={endRef} />
        </div>
        <ErrorBanner error={error} onClose={() => setError(null)} />
        {showUpload && <div className="chat-upload"><ImageUpload file={image} onChange={setImage} label="Attach image" optional /></div>}
        <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send() }}>
          <button type="button" className={`icon-btn ${image ? 'on' : ''}`} title="Attach image" onClick={() => setShowUpload((s) => !s)}>📎</button>
          <textarea rows={1} value={input} maxLength={8000} placeholder="Ask a construction question…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
          <button className="btn" disabled={loading || !input.trim()}>Send</button>
          {messages.length > 0 && <button type="button" className="link-btn" onClick={() => setMessages([])}>Clear</button>}
        </form>
      </div>
    </>
  )
}

function Answer({ m, onAsk }) {
  const d = m.data || {}
  return (
    <div>
      {d.in_scope === false && <Badge value="caution" text="Outside construction scope" />}
      <Markdown text={m.content} />
      {arr(d.key_points).length > 0 && (
        <details open><summary>Key points</summary><ul className="list">{d.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul></details>
      )}
      {arr(d.code_references).length > 0 && (
        <div className="refs">{d.code_references.map((r, i) => <span className="tag" key={i}>📘 {r}</span>)}</div>
      )}
      {arr(d.safety_considerations).length > 0 && (
        <details><summary>Safety considerations</summary><ul className="list">{d.safety_considerations.map((k, i) => <li key={i}>{k}</li>)}</ul></details>
      )}
      {arr(d.follow_up_questions).length > 0 && (
        <div className="chips">{d.follow_up_questions.slice(0, 3).map((q, i) => <button key={i} className="chip small" onClick={() => onAsk(q)}>{q}</button>)}</div>
      )}
      <div className="small muted bubble-meta">
        {m.meta?.mode === 'demo' ? 'Demo mode' : m.meta?.model} · confidence {Math.round(num(d.confidence) * 100)}%
      </div>
    </div>
  )
}
