import { useState } from 'react'
import { api } from '../api'
import { BarList, FloorPlan, GanttChart } from '../components/Charts'
import { IconPlanning } from '../components/Icons'
import { Card, ErrorBanner, Field, List, Loading, PageHeader, ResultMeta, Stat } from '../components/ui'
import { useApi } from '../useApi'
import { arr, label, money, num } from '../utils'

export default function Planning() {
  const [f, setF] = useState({
    project_name: 'Green Residency', project_type: 'residential', location: 'Pune, Maharashtra',
    built_up_area_sqft: 3200, floors: 3, structure_type: 'rcc_frame', quality_tier: 'standard', currency: 'INR',
    start_date: '', special_requirements: '',
  })
  const { loading, error, result, run, setError } = useApi()
  const set = (k, numeric = false) => (e) => setF({ ...f, [k]: numeric ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value })

  const submit = (e) => {
    e.preventDefault()
    if (!(num(f.built_up_area_sqft) > 0) || !(num(f.floors) >= 1)) return setError({ message: 'Area must be positive and floors at least 1.' })
    run(() => api.planning(f))
  }
  const d = result?.data
  const cur = d?.currency || f.currency
  const concept = d?.architectural_concept || {}

  return (
    <>
      <PageHeader icon={<IconPlanning size={28} color="var(--accent)" />} title="Construction Planning & Estimation"
        subtitle="Material quantities, cost breakdown, AI schedule with critical path, and an architectural concept." />
      <div className="layout-2">
        <Card title="Project brief">
          <form onSubmit={submit} className="form">
            <Field label="Project name"><input value={f.project_name} maxLength={120} onChange={set('project_name')} /></Field>
            <Field label="Location"><input value={f.location} maxLength={200} onChange={set('location')} required /></Field>
            <div className="grid-2">
              <Field label="Project type">
                <select value={f.project_type} onChange={set('project_type')}>
                  {['residential', 'commercial', 'industrial', 'institutional'].map((x) => <option key={x} value={x}>{label(x)}</option>)}
                </select>
              </Field>
              <Field label="Currency">
                <select value={f.currency} onChange={set('currency')}><option>INR</option><option>USD</option></select>
              </Field>
              <Field label="Built-up area (sqft)"><input type="number" min="1" value={f.built_up_area_sqft} onChange={set('built_up_area_sqft', true)} required /></Field>
              <Field label="Floors"><input type="number" min="1" max="100" value={f.floors} onChange={set('floors', true)} required /></Field>
              <Field label="Structure">
                <select value={f.structure_type} onChange={set('structure_type')}>
                  {['rcc_frame', 'load_bearing', 'steel_frame'].map((x) => <option key={x} value={x}>{label(x)}</option>)}
                </select>
              </Field>
              <Field label="Quality">
                <select value={f.quality_tier} onChange={set('quality_tier')}>
                  {['economy', 'standard', 'premium'].map((x) => <option key={x} value={x}>{label(x)}</option>)}
                </select>
              </Field>
            </div>
            <Field label="Planned start"><input type="date" value={f.start_date} onChange={set('start_date')} /></Field>
            <Field label="Special requirements (optional)">
              <textarea rows={3} maxLength={2000} value={f.special_requirements} onChange={set('special_requirements')}
                placeholder="e.g. basement parking, green building certification" />
            </Field>
            <button className="btn" disabled={loading}>{loading ? 'Planning…' : 'Generate plan'}</button>
          </form>
        </Card>

        <div className="stack">
          <ErrorBanner error={error} onClose={() => setError(null)} />
          {loading && <Loading text="Estimating materials and building the schedule…" />}
          {!d && !loading && <Card><p className="muted">Enter the project brief to generate quantities, costs, a Gantt schedule and a concept design.</p></Card>}
          {d && (
            <>
              <Card>
                <div className="stats">
                  <Stat label="Total project cost" value={money(d.total_cost, cur)} hint={`incl. ${money(d.contingency, cur)} contingency`} />
                  <Stat label="Cost / sqft" value={money(d.cost_per_sqft, cur)} />
                  <Stat label="Duration" value={`${d.total_duration_days} days`} hint={`≈ ${(num(d.total_duration_days) / 26).toFixed(1)} months (26 working days)`} />
                  <Stat label="Tasks" value={arr(d.schedule).length} />
                </div>
              </Card>
              <Card title="Cost breakdown">
                <BarList items={d.cost_breakdown} format={(v, i) => `${money(v, cur)} · ${i.percent}%`} />
              </Card>
              <Card title="Material estimate">
                <table className="table">
                  <thead><tr><th>Material</th><th className="num">Quantity</th><th>Unit</th><th className="num">Rate</th><th className="num">Cost</th></tr></thead>
                  <tbody>
                    {arr(d.materials).map((m, i) => (
                      <tr key={i}><td>{m.material}</td><td className="num">{num(m.quantity).toLocaleString()}</td><td>{m.unit}</td>
                        <td className="num">{num(m.unit_rate).toLocaleString()}</td><td className="num">{money(m.cost, cur)}</td></tr>
                    ))}
                  </tbody>
                  <tfoot><tr><td colSpan={4}>Core materials total</td><td className="num">{money(d.material_cost, cur)}</td></tr></tfoot>
                </table>
              </Card>
              <Card title="Schedule (Gantt)">
                <GanttChart tasks={d.schedule} total={d.total_duration_days} />
                <p className="small muted">Critical path: {arr(d.critical_path).join(' → ') || '—'}</p>
              </Card>
              <Card title={`Architectural concept · ${concept.style || ''}`}>
                <div className="concept">
                  <div>
                    <p>{concept.description}</p>
                    <div className="palette">
                      {arr(concept.facade_palette).filter((c) => /^#[0-9a-f]{3,8}$/i.test(c)).map((c) => (
                        <span key={c} style={{ background: c }} title={c} />
                      ))}
                    </div>
                    <h4>Design features</h4><List items={concept.design_features} />
                    <h4>Sustainability</h4><List items={concept.sustainability_features} />
                  </div>
                  <div><h4>Typical floor layout</h4><FloorPlan rooms={concept.floor_plan} /></div>
                </div>
              </Card>
              <div className="grid-2">
                <Card title="Risks"><List items={d.risks} /></Card>
                <Card title="Recommendations"><List items={d.recommendations} /></Card>
              </div>
              <Card title="Assumptions"><List items={d.assumptions} /></Card>
              <ResultMeta meta={result.meta} data={d} />
            </>
          )}
        </div>
      </div>
    </>
  )
}
