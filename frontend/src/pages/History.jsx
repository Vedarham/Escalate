import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card, ErrorBanner, PageHeader } from '../components/ui'
import { arr } from '../utils'

const MODULES = ['', 'safety', 'crack', 'valuation', 'planning', 'daily', 'chat', 'legal']

export default function History() {
  const [module, setModule] = useState('')
  const [items, setItems] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setItems(null)
    api.history(module).then((r) => setItems(r.data.items)).catch((e) => { setError(e); setItems([]) })
  }, [module])

  const open = (id) => api.historyItem(id).then((r) => setSelected(r.data)).catch(setError)

  return (
    <>
      <PageHeader icon="🗂" title="Analysis History" subtitle="Every AI result is stored with its inputs for audit and reporting." />
      <ErrorBanner error={error} onClose={() => setError(null)} />
      <div className="layout-2">
        <Card title="Records" actions={
          <select value={module} onChange={(e) => setModule(e.target.value)}>
            {MODULES.map((m) => <option key={m} value={m}>{m || 'All modules'}</option>)}
          </select>
        }>
          {!items && <p className="muted">Loading…</p>}
          {items && items.length === 0 && <p className="muted">No records.</p>}
          <ul className="activity selectable">
            {arr(items).map((i) => (
              <li key={i.id} className={selected?.id === i.id ? 'active' : ''} onClick={() => open(i.id)}>
                <span className="tag">{i.module}</span> #{i.id} {i.title}
                <div className="small muted">{new Date(i.created_at).toLocaleString()} · {i.mode} · {i.provider}</div>
              </li>
            ))}
          </ul>
        </Card>
        <Card title={selected ? `Record #${selected.id}` : 'Details'}>
          {!selected && <p className="muted">Select a record to view its stored input and JSON output.</p>}
          {selected && (
            <>
              {selected.image_file && <img className="history-img" src={api.imageUrl(selected.image_file)} alt="Analysed upload" />}
              <h4>Input</h4>
              <pre className="json">{JSON.stringify(selected.input, null, 2)}</pre>
              <h4>Output</h4>
              <pre className="json">{JSON.stringify(selected.output, null, 2)}</pre>
            </>
          )}
        </Card>
      </div>
    </>
  )
}
