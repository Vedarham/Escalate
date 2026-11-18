import { useState } from 'react'
import { api } from '../api'
import { IconCracks, IconShield } from '../components/Icons'
import ImageUpload from '../components/ImageUpload'
import { Badge, Card, Confidence, ErrorBanner, Field, List, Loading, PageHeader, ResultMeta } from '../components/ui'
import { useApi } from '../useApi'
import { arr } from '../utils'

export default function Cracks() {
  const [image, setImage] = useState(null)
  const [f, setF] = useState({ element_type: 'wall', material: 'Brick masonry with plaster', building_age_years: '', notes: '' })
  const { loading, error, result, run, setError } = useApi()
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  const submit = (e) => {
    e.preventDefault()
    if (!image) return setError({ message: 'Please upload a photo of the crack.' })
    run(() => api.crack(image, f))
  }
  const d = result?.data

  return (
    <>
      <PageHeader icon={<IconCracks size={28} color="var(--accent)" />} title="Structural Crack Analysis"
        subtitle="Classify cracks, estimate severity, find probable causes and repair methods." />
      <div className="layout-2">
        <Card title="Input">
          <form onSubmit={submit} className="form">
            <ImageUpload file={image} onChange={setImage} label="Upload crack close-up" />
            <div className="grid-2">
              <Field label="Element">
                <select value={f.element_type} onChange={set('element_type')}>
                  {['wall', 'beam', 'column', 'slab', 'foundation', 'retaining wall', 'pavement', 'ceiling'].map((x) => <option key={x}>{x}</option>)}
                </select>
              </Field>
              <Field label="Building age (years)">
                <input type="number" min="0" max="300" value={f.building_age_years} onChange={set('building_age_years')} placeholder="e.g. 12" />
              </Field>
            </div>
            <Field label="Material"><input value={f.material} maxLength={80} onChange={set('material')} /></Field>
            <Field label="Observations (optional)">
              <textarea rows={3} maxLength={2000} value={f.notes} onChange={set('notes')}
                placeholder="e.g. crack appeared after monsoon, door is sticking" />
            </Field>
            <button className="btn" disabled={loading}>{loading ? 'Analysing…' : 'Analyse crack'}</button>
          </form>
        </Card>

        <div className="stack">
          <ErrorBanner error={error} onClose={() => setError(null)} />
          {loading && <Loading text="Measuring and classifying cracks…" />}
          {!d && !loading && <Card><p className="muted">Tip: place a coin or scale next to the crack for better width estimates.</p></Card>}
          {d && (
            <>
              <Card>
                <div className="row between wrap">
                  <div className="row gap">
                    <span className="muted">Overall severity</span><Badge value={d.overall_severity} />
                    {d.structural_concern && <Badge value="critical" text="Structural concern" />}
                    {d.requires_engineer_inspection && <Badge value="high" text="Engineer inspection required" />}
                  </div>
                  <Confidence value={d.confidence} />
                </div>
                <p>{d.surface_description}</p>
                {!d.crack_detected && <p className="ok-text">No significant cracks detected.</p>}
              </Card>
              {arr(d.cracks).length > 0 && (
                <Card title="Detected cracks">
                  {arr(d.cracks).map((c, i) => (
                    <div className="item" key={i}>
                      <div className="row between"><strong>#{i + 1} {c.crack_type}</strong><Badge value={c.severity} /></div>
                      <div className="kv">
                        <span>Orientation</span><span>{c.orientation}</span>
                        <span>Width</span><span>{c.estimated_width_mm} mm</span>
                        <span>Length</span><span>{c.estimated_length}</span>
                        <span>Location</span><span>{c.location}</span>
                      </div>
                    </div>
                  ))}
                </Card>
              )}
              <Card title="Probable causes">
                {arr(d.probable_causes).map((c, i) => (
                  <div className="item" key={i}>
                    <div className="row between"><strong>{c.cause}</strong><Badge value={c.likelihood} text={`${c.likelihood} likelihood`} /></div>
                    <p className="small">{c.explanation}</p>
                  </div>
                ))}
              </Card>
              <Card title="Recommended corrective actions">
                {arr(d.recommended_actions).map((a, i) => (
                  <div className="item" key={i}>
                    <div className="row between"><strong>{a.action}</strong><Badge value={a.priority} /></div>
                    <p className="small"><IconShield size={13} /> {a.method}</p>
                  </div>
                ))}
              </Card>
              <Card title="Monitoring plan"><p>{d.monitoring_plan}</p><p className="small muted">{d.disclaimer}</p></Card>
              <ResultMeta meta={result.meta} data={d} />
            </>
          )}
        </div>
      </div>
    </>
  )
}
