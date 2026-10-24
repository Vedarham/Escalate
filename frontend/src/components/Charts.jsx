import { arr, num, str } from '../utils'

const PHASE_COLORS = ['#6366f1', '#0ea5e9', '#14b8a6', '#f59e0b', '#ec4899', '#8b5cf6', '#22c55e', '#ef4444']

export function GanttChart({ tasks, total }) {
  const list = arr(tasks)
  const span = Math.max(1, num(total) || Math.max(1, ...list.map((t) => num(t.end_day))))
  const phases = [...new Set(list.map((t) => str(t.phase)))]
  const colorOf = (p) => PHASE_COLORS[phases.indexOf(p) % PHASE_COLORS.length]
  const ticks = 6
  if (!list.length) return <p className="muted">No schedule available.</p>
  return (
    <div className="gantt">
      <div className="gantt-row gantt-axis">
        <div className="gantt-label" />
        <div className="gantt-track">
          {Array.from({ length: ticks + 1 }, (_, i) => (
            <span key={i} style={{ left: `${(i / ticks) * 100}%` }}>Day {Math.round((span * i) / ticks)}</span>
          ))}
        </div>
      </div>
      {list.map((t) => {
        const left = (num(t.start_day) / span) * 100
        const width = Math.max(0.8, (num(t.duration_days) / span) * 100)
        return (
          <div className="gantt-row" key={t.id}>
            <div className="gantt-label" title={t.resources}>
              <span className="gantt-id">{t.id}</span> {t.task}
            </div>
            <div className="gantt-track">
              <div
                className={`gantt-bar ${t.critical ? 'critical' : ''}`}
                style={{ left: `${left}%`, width: `${width}%`, background: colorOf(str(t.phase)) }}
                title={`${t.task}\nDay ${t.start_day}–${t.end_day} (${t.duration_days} d)\nDepends on: ${arr(t.depends_on).join(', ') || '—'}`}
              >
                <span>{t.duration_days}d</span>
              </div>
            </div>
          </div>
        )
      })}
      <div className="legend">
        {phases.map((p) => <span key={p}><i style={{ background: colorOf(p) }} />{p}</span>)}
        <span><i className="crit-swatch" />Critical path</span>
      </div>
    </div>
  )
}

const ROOM_FILL = ['#fef3c7', '#dbeafe', '#dcfce7', '#fce7f3', '#ede9fe', '#ffedd5', '#cffafe', '#f1f5f9', '#fee2e2', '#e0e7ff']

export function FloorPlan({ rooms }) {
  const list = arr(rooms)
  if (!list.length) return <p className="muted">No layout generated.</p>
  return (
    <svg viewBox="-2 -2 104 104" className="floorplan" role="img" aria-label="Conceptual floor plan">
      <rect x="0" y="0" width="100" height="100" className="fp-outline" />
      {list.map((r, i) => {
        const x = num(r.x), y = num(r.y)
        const w = Math.min(num(r.width, 10), 100 - x), h = Math.min(num(r.height, 10), 100 - y)
        const fs = Math.max(2.2, Math.min(4, w / Math.max(6, str(r.name).length * 0.9)))
        return (
          <g key={i}>
            <rect x={x} y={y} width={w} height={h} fill={ROOM_FILL[i % ROOM_FILL.length]} className="fp-room" />
            <text x={x + w / 2} y={y + h / 2} fontSize={fs} textAnchor="middle" dominantBaseline="middle" className="fp-text">
              {str(r.name)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export function BarList({ items, valueKey = 'amount', labelKey = 'category', format = (v) => v }) {
  const list = arr(items)
  const max = Math.max(1, ...list.map((i) => num(i[valueKey])))
  return (
    <div className="barlist">
      {list.map((i, idx) => (
        <div className="barlist-row" key={idx}>
          <span className="barlist-label">{str(i[labelKey])}</span>
          <div className="barlist-track">
            <div style={{ width: `${(num(i[valueKey]) / max) * 100}%`, background: PHASE_COLORS[idx % PHASE_COLORS.length] }} />
          </div>
          <span className="barlist-value">{format(num(i[valueKey]), i)}</span>
        </div>
      ))}
    </div>
  )
}
