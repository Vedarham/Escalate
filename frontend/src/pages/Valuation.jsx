import { useState } from 'react'
import { api } from '../api'
import { BarList } from '../components/Charts'
import ImageUpload from '../components/ImageUpload'
import { Badge, Card, Confidence, ErrorBanner, Field, List, Loading, PageHeader, ResultMeta, Stat } from '../components/ui'
import { useApi } from '../useApi'
import { arr, label, money, num } from '../utils'

const TYPES = ['apartment', 'independent_house', 'villa', 'plot', 'commercial_office', 'retail_shop', 'warehouse']
const CONDITIONS = ['new', 'excellent', 'good', 'fair', 'needs_renovation']
const AMENITIES = ['Parking', 'Lift', 'Power backup', 'Gym', 'Swimming pool', 'Security', 'Clubhouse', 'Garden', 'Metro nearby', 'School nearby']

export default function Valuation() {
  const [f, setF] = useState({
    location: 'Whitefield, Bengaluru', property_type: 'apartment', built_up_area_sqft: 1450, plot_area_sqft: 0,
    bedrooms: 3, bathrooms: 2, age_years: 4, floor: 6, condition: 'good', amenities: ['Parking', 'Lift', 'Gym'],
    currency: 'INR', notes: '',
  })
  const [image, setImage] = useState(null)
  const { loading, error, result, run, setError } = useApi()
  const set = (k, numeric = false) => (e) => setF({ ...f, [k]: numeric ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value })
  const toggle = (a) => setF({ ...f, amenities: f.amenities.includes(a) ? f.amenities.filter((x) => x !== a) : [...f.amenities, a] })

  const submit = (e) => {
    e.preventDefault()
    if (!f.location.trim() || !(num(f.built_up_area_sqft) > 0)) return setError({ message: 'Location and a positive built-up area are required.' })
    const numeric = ['built_up_area_sqft', 'plot_area_sqft', 'bedrooms', 'bathrooms', 'age_years', 'floor']
    const payload = { ...f, location: f.location.trim() }
    numeric.forEach((k) => { payload[k] = num(Number(f[k])) })
    run(() => api.valuation(payload, image))
  }
  const d = result?.data
  const cur = d?.currency || f.currency

  return (
    <>
      <PageHeader icon="🏠" title="Real Estate Valuation" subtitle="AI-assisted market value estimate from property details and photos." />
      <div className="layout-2">
        <Card title="Property details">
          <form onSubmit={submit} className="form">
            <Field label="Location"><input value={f.location} onChange={set('location')} maxLength={200} required /></Field>
            <div className="grid-2">
              <Field label="Property type">
                <select value={f.property_type} onChange={set('property_type')}>{TYPES.map((t) => <option key={t} value={t}>{label(t)}</option>)}</select>
              </Field>
              <Field label="Currency">
                <select value={f.currency} onChange={set('currency')}><option>INR</option><option>USD</option></select>
              </Field>
              <Field label="Built-up area (sqft)"><input type="number" min="1" value={f.built_up_area_sqft} onChange={set('built_up_area_sqft', true)} required /></Field>
              <Field label="Plot area (sqft)"><input type="number" min="0" value={f.plot_area_sqft} onChange={set('plot_area_sqft', true)} /></Field>
              <Field label="Bedrooms"><input type="number" min="0" max="50" value={f.bedrooms} onChange={set('bedrooms', true)} /></Field>
              <Field label="Bathrooms"><input type="number" min="0" max="50" value={f.bathrooms} onChange={set('bathrooms', true)} /></Field>
              <Field label="Age (years)"><input type="number" min="0" max="200" value={f.age_years} onChange={set('age_years', true)} /></Field>
              <Field label="Floor"><input type="number" min="-5" max="200" value={f.floor} onChange={set('floor', true)} /></Field>
            </div>
            <Field label="Condition">
              <select value={f.condition} onChange={set('condition')}>{CONDITIONS.map((c) => <option key={c} value={c}>{label(c)}</option>)}</select>
            </Field>
            <div className="field">
              <span className="field-label">Amenities</span>
              <div className="chips">
                {AMENITIES.map((a) => (
                  <button type="button" key={a} className={`chip ${f.amenities.includes(a) ? 'on' : ''}`} onClick={() => toggle(a)}>{a}</button>
                ))}
              </div>
            </div>
            <ImageUpload file={image} onChange={setImage} label="Property photo" optional />
            <button className="btn" disabled={loading}>{loading ? 'Estimating…' : 'Estimate value'}</button>
          </form>
        </Card>

        <div className="stack">
          <ErrorBanner error={error} onClose={() => setError(null)} />
          {loading && <Loading text="Comparing market benchmarks…" />}
          {!d && !loading && <Card><p className="muted">Fill in the property details to get a value range, key value drivers and market outlook.</p></Card>}
          {d && (
            <>
              <Card>
                <div className="value-hero">
                  <div className="muted small">Estimated market value</div>
                  <div className="value-mid">{money(d.estimated_value?.mid, cur)}</div>
                  <div className="value-range">
                    Range {money(d.estimated_value?.low, cur)} – {money(d.estimated_value?.high, cur)}
                  </div>
                </div>
                <div className="stats">
                  <Stat label="Price / sqft" value={money(d.price_per_sqft, cur)} />
                  <Stat label="Gross rental yield" value={`${num(d.rental_yield_percent).toFixed(1)}%`} />
                </div>
                <Confidence value={d.confidence} />
              </Card>
              <Card title="Value drivers">
                <BarList items={d.valuation_factors} valueKey="weight_percent" labelKey="factor" format={(v) => `${Math.round(v)}%`} />
                {arr(d.valuation_factors).map((x, i) => (
                  <div className="item" key={i}>
                    <div className="row between"><strong>{x.factor}</strong><Badge value={x.impact} /></div>
                    <p className="small">{x.explanation}</p>
                  </div>
                ))}
              </Card>
              {d.image_observations && <Card title="Photo observations"><p>{d.image_observations}</p></Card>}
              <Card title="Market insights"><List items={d.market_insights} /></Card>
              <Card title="Comparable assumptions"><List items={d.comparable_assumptions} /></Card>
              <Card title="Investment outlook"><p>{d.investment_outlook}</p><p className="small muted">{d.disclaimer}</p></Card>
              <ResultMeta meta={result.meta} data={d} />
            </>
          )}
        </div>
      </div>
    </>
  )
}
