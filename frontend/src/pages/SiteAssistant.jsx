import { useState } from 'react'
import { api } from '../api'
import { Badge, Card, ErrorBanner, Field, List, Loading, PageHeader, ResultMeta } from '../components/ui'
import { useApi } from '../useApi'
import { arr, num } from '../utils'

const SUIT_TEXT = { go: 'Good to go', caution: 'Proceed with caution', no_go: 'No-go day' }

export default function SiteAssistant() {
  const [f, setF] = useState({
    location: 'Chennai', project_phase: 'Superstructure', crew_size: 25, concerns: '',
    activities: 'Slab concrete pour (3rd floor)\nScaffolding erection on east face\nInternal blockwork',
  })
  const { loading, error, result, run, setError } = useApi()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = (e) => {
    e.preventDefault()
    if (f.location.trim().length < 2) return setError({ message: 'Please enter the site location (city).' })
    run(() => api.daily({
      location: f.location.trim(), project_phase: f.project_phase, crew_size: Number(f.crew_size) || 0,
      concerns: f.concerns, planned_activities: f.activities.split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 20),
    }))
  }
  const d = result?.data
  const w = d?.weather

  return (
    <>
      <PageHeader icon="🌦" title="Daily Site Assistant & Weather Advisory"
        subtitle="Live forecast + AI go/no-go guidance for today's planned activities." />
      <div className="layout-2">
        <Card title="Today's plan">
          <form onSubmit={submit} className="form">
            <Field label="Site location (city)"><input value={f.location} maxLength={120} onChange={set('location')} required /></Field>
            <div className="grid-2">
              <Field label="Project phase"><input value={f.project_phase} maxLength={120} onChange={set('project_phase')} /></Field>
              <Field label="Crew size"><input type="number" min="0" max="5000" value={f.crew_size} onChange={set('crew_size')} /></Field>
            </div>
            <Field label="Planned activities" hint="One per line">
              <textarea rows={5} value={f.activities} onChange={set('activities')} />
            </Field>
            <Field label="Concerns (optional)"><textarea rows={2} maxLength={2000} value={f.concerns} onChange={set('concerns')} /></Field>
            <button className="btn" disabled={loading}>{loading ? 'Preparing…' : 'Get daily advisory'}</button>
          </form>
        </Card>

        <div className="stack">
          <ErrorBanner error={error} onClose={() => setError(null)} />
          {loading && <Loading text="Fetching forecast and preparing the advisory…" />}
          {!d && !loading && <Card><p className="muted">Get a weather-aware plan, toolbox talk topic and checklist for the day.</p></Card>}
          {d && (
            <>
              <Card>
                <div className="row between wrap">
                  <div>
                    <div className="muted small">Work suitability</div>
                    <div className="row gap"><Badge value={d.work_suitability} text={SUIT_TEXT[d.work_suitability] || d.work_suitability} /></div>
                  </div>
                  {w?.available && (
                    <div className="right">
                      <div className="big">{num(w.current_temp_c).toFixed(0)}°C</div>
                      <div className="small muted">{w.current_condition} · {w.location_name}</div>
                    </div>
                  )}
                </div>
                <p>{d.weather_summary}</p>
                {w?.available && (
                  <div className="forecast">
                    {arr(w.days).map((day) => (
                      <div key={day.date} className="forecast-day">
                        <strong>{new Date(day.date + 'T00:00').toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })}</strong>
                        <span>{day.condition}</span>
                        <span>{day.temp_min_c ?? '–'}° / {day.temp_max_c ?? '–'}°C</span>
                        <span>💧 {day.precipitation_mm ?? 0} mm ({day.precipitation_probability ?? 0}%)</span>
                        <span>💨 {day.wind_max_kmh ?? '–'} km/h</span>
                      </div>
                    ))}
                  </div>
                )}
                {arr(w?.alerts).length > 0 && <div className="alert alert-warn"><List items={w.alerts} /></div>}
              </Card>
              <Card title="Activity recommendations">
                {arr(d.activity_recommendations).map((a, i) => (
                  <div className="item" key={i}>
                    <div className="row between"><strong>{a.activity}</strong><Badge value={a.recommendation} /></div>
                    <p className="small">{a.reason}</p>
                    <List items={a.precautions} empty="" />
                  </div>
                ))}
              </Card>
              <div className="grid-2">
                <Card title="Safety briefing"><List items={d.safety_briefing} /></Card>
                <Card title="Toolbox talk"><p><strong>{d.toolbox_talk_topic}</strong></p></Card>
                <Card title="Material protection"><List items={d.material_protection} /></Card>
                <Card title="Productivity tips"><List items={d.productivity_tips} /></Card>
              </div>
              <Card title="Daily checklist">
                <ul className="checklist">
                  {arr(d.daily_checklist).map((c, i) => <li key={i}><label><input type="checkbox" /> {c}</label></li>)}
                </ul>
              </Card>
              <ResultMeta meta={result.meta} data={d} />
            </>
          )}
        </div>
      </div>
    </>
  )
}
