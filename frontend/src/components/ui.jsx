import { useState } from 'react'
import { arr, label, num, str, tone } from '../utils'

export function Badge({ value, text }) {
  return <span className={`badge badge-${tone(value)}`}>{text ?? label(value)}</span>
}

export function Card({ title, children, actions, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-head">
          {title && <h3>{title}</h3>}
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}

export function PageHeader({ icon, title, subtitle }) {
  return (
    <div className="page-header">
      <div className="page-icon" aria-hidden>{icon}</div>
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
    </div>
  )
}

export function ScoreRing({ value, max = 100, caption, invert = false }) {
  const v = Math.max(0, Math.min(max, num(value)))
  const ratio = v / max
  const good = invert ? 1 - ratio : ratio
  const color = good >= 0.75 ? 'var(--ok)' : good >= 0.5 ? 'var(--warn)' : 'var(--bad)'
  const r = 42
  const c = 2 * Math.PI * r
  return (
    <div className="ring">
      <svg viewBox="0 0 100 100" width="112" height="112" role="img" aria-label={`${caption}: ${Math.round(v)}`}>
        <circle cx="50" cy="50" r={r} className="ring-track" />
        <circle cx="50" cy="50" r={r} stroke={color} className="ring-value"
          strokeDasharray={`${c * ratio} ${c}`} transform="rotate(-90 50 50)" />
        <text x="50" y="55" textAnchor="middle" className="ring-text">{Math.round(v)}</text>
      </svg>
      {caption && <div className="ring-caption">{caption}</div>}
    </div>
  )
}

export function Stat({ label: l, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-label">{l}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  )
}

export function List({ items, empty = 'None reported.' }) {
  const list = arr(items).filter(Boolean)
  if (!list.length) return <p className="muted">{empty}</p>
  return <ul className="list">{list.map((x, i) => <li key={i}>{str(x)}</li>)}</ul>
}

export function ErrorBanner({ error, onClose }) {
  if (!error) return null
  const details = arr(error.details)
  return (
    <div className="alert alert-error" role="alert">
      <div>
        <strong>{error.message || 'Something went wrong.'}</strong>
        {details.length > 0 && (
          <ul className="list small">
            {details.slice(0, 6).map((d, i) => (
              <li key={i}>{typeof d === 'string' ? d : `${d.field ? d.field + ': ' : ''}${d.message ?? JSON.stringify(d)}`}</li>
            ))}
          </ul>
        )}
      </div>
      {onClose && <button className="icon-btn" onClick={onClose} aria-label="Dismiss">×</button>}
    </div>
  )
}

export function Loading({ text = 'Analysing…' }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" /> {text}
    </div>
  )
}

export function ResultMeta({ meta, data }) {
  const [showJson, setShowJson] = useState(false)
  if (!meta) return null
  const warnings = arr(meta.warnings)
  return (
    <div className="meta">
      <div className="meta-row">
        <Badge value={meta.mode === 'live' ? 'go' : 'caution'} text={meta.mode === 'live' ? 'Live AI' : 'Demo mode'} />
        <span className="muted small">
          {meta.provider} · {meta.model} · {(num(meta.latency_ms) / 1000).toFixed(1)}s
          {meta.record_id ? ` · record #${meta.record_id}` : ''}
        </span>
        <button className="link-btn" onClick={() => setShowJson((s) => !s)}>
          {showJson ? 'Hide' : 'View'} JSON contract
        </button>
      </div>
      {warnings.length > 0 && (
        <div className="alert alert-warn">
          <ul className="list small">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
      {showJson && <pre className="json">{JSON.stringify({ data, meta }, null, 2)}</pre>}
    </div>
  )
}

export function Field({ label: l, children, hint }) {
  return (
    <label className="field">
      <span className="field-label">{l}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  )
}

export function Confidence({ value }) {
  const v = Math.max(0, Math.min(1, num(value)))
  return (
    <div className="confidence" title="Model confidence">
      <span className="muted small">Confidence</span>
      <div className="bar"><div style={{ width: `${v * 100}%` }} /></div>
      <span className="small">{Math.round(v * 100)}%</span>
    </div>
  )
}

const CITE_RE = /(\[[A-Z]{2}(?:-[A-Z]{2,3})*-\d{2}\])/ // capture group -> split keeps the ids
const CITE_ONE = /^\[[A-Z]{2}(?:-[A-Z]{2,3})*-\d{2}\]$/

/** Minimal, XSS-safe markdown: paragraphs, "- " bullets, **bold**, and optional [ID] citation chips. */
export function Markdown({ text, onCite }) {
  const lines = str(text).split('\n')
  const blocks = []
  let bullets = []
  const flush = () => {
    if (bullets.length) blocks.push(<ul className="list" key={blocks.length}>{bullets}</ul>)
    bullets = []
  }
  const cites = (s, key) =>
    !onCite ? s : s.split(CITE_RE).map((part, i) =>
      CITE_ONE.test(part)
        ? <button type="button" key={`${key}-${i}`} className="cite" onClick={() => onCite(part.slice(1, -1))}>{part.slice(1, -1)}</button>
        : part)
  const inline = (s) =>
    s.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
      part.startsWith('**') && part.endsWith('**')
        ? <strong key={i}>{cites(part.slice(2, -2), i)}</strong>
        : <span key={i}>{cites(part.replace(/\*/g, ''), i)}</span>)
  lines.forEach((line, i) => {
    const m = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)/)
    if (m) bullets.push(<li key={i}>{inline(m[1])}</li>)
    else {
      flush()
      if (line.trim()) blocks.push(<p key={`p${i}`}>{inline(line)}</p>)
    }
  })
  flush()
  return <div className="md">{blocks}</div>
}
