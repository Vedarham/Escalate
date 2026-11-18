import { useState } from 'react'
import { api } from '../api'
import { IconBook, IconLocation, IconSafety } from '../components/Icons'
import ImageUpload from '../components/ImageUpload'
import { Badge, Card, Confidence, ErrorBanner, Field, List, Loading, PageHeader, ResultMeta, ScoreRing, Stat } from '../components/ui'
import { useApi } from '../useApi'
import { arr } from '../utils'

export default function Safety() {
  const [image, setImage] = useState(null)
  const [context, setContext] = useState('')
  const [siteType, setSiteType] = useState('building')
  const { loading, error, result, run, setError } = useApi()

  const submit = (e) => {
    e.preventDefault()
    if (!image) return setError({ message: 'Please upload a construction site photo first.' })
    run(() => api.safety(image, context, siteType))
  }
  const d = result?.data

  return (
    <>
      <PageHeader icon={<IconSafety size={28} color="var(--accent)" />} title="Site Safety Monitoring"
        subtitle="Detect hazards and PPE compliance issues from jobsite photos." />
      <div className="layout-2">
        <Card title="Input">
          <form onSubmit={submit} className="form">
            <ImageUpload file={image} onChange={setImage} label="Upload jobsite photo" />
            <Field label="Site type">
              <select value={siteType} onChange={(e) => setSiteType(e.target.value)}>
                {['building', 'high-rise', 'road / highway', 'bridge', 'excavation', 'industrial', 'renovation'].map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="Context (optional)" hint="Activity in progress, known issues…">
              <textarea rows={3} maxLength={2000} value={context} onChange={(e) => setContext(e.target.value)}
                placeholder="e.g. Slab shuttering on 4th floor, 8 workers" />
            </Field>
            <button className="btn" disabled={loading}>{loading ? 'Analysing…' : 'Analyse safety'}</button>
          </form>
        </Card>

        <div className="stack">
          <ErrorBanner error={error} onClose={() => setError(null)} />
          {loading && <Loading text="Inspecting the site for hazards…" />}
          {!d && !loading && <Card><p className="muted">Upload a photo to get a hazard report, PPE audit and corrective actions.</p></Card>}
          {d && (
            <>
              <Card>
                <div className="summary-row">
                  <ScoreRing value={d.safety_score} caption="Safety score" />
                  <div className="grow">
                    <div className="row gap">
                      <span className="muted">Overall risk</span> <Badge value={d.overall_risk_level} />
                    </div>
                    <p>{d.scene_summary}</p>
                    <div className="stats">
                      <Stat label="Workers detected" value={d.workers_detected} />
                      <Stat label="Hazards" value={arr(d.hazards).length} />
                    </div>
                    <Confidence value={d.confidence} />
                  </div>
                </div>
              </Card>
              <Card title="Immediate actions" className="accent-bad"><List items={d.immediate_actions} /></Card>
              <Card title="Hazards">
                {arr(d.hazards).length === 0 && <p className="muted">No hazards identified.</p>}
                {arr(d.hazards).map((h, i) => (
                  <div className="item" key={i}>
                    <div className="row between">
                      <strong>{h.category}</strong> <Badge value={h.severity} />
                    </div>
                    <p>{h.description}</p>
                    <div className="small muted">
                      <IconLocation size={13} /> {h.location_in_image || '—'} {h.regulation_reference && <><span style={{ margin: '0 4px' }}>·</span><IconBook size={13} /> {h.regulation_reference}</>}
                    </div>
                    <div className="small"><strong>Action:</strong> {h.recommended_action}</div>
                  </div>
                ))}
              </Card>
              <Card title="PPE compliance">
                <table className="table">
                  <thead><tr><th>Item</th><th>Status</th><th>Workers</th><th>Observation</th></tr></thead>
                  <tbody>
                    {arr(d.ppe_compliance).map((p, i) => (
                      <tr key={i}><td>{p.item}</td><td><Badge value={p.status} /></td><td>{p.workers_affected || '—'}</td><td>{p.observation}</td></tr>
                    ))}
                  </tbody>
                </table>
              </Card>
              <Card title="Good practices observed"><List items={d.positive_observations} /></Card>
              <ResultMeta meta={result.meta} data={d} />
            </>
          )}
        </div>
      </div>
    </>
  )
}
