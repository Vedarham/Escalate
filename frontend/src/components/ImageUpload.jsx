import { useEffect, useRef, useState } from 'react'
import { checkImage, MAX_IMAGE_MB } from '../utils'

export default function ImageUpload({ file, onChange, label = 'Upload a photo', optional = false }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [drag, setDrag] = useState(false)
  const input = useRef(null)

  useEffect(() => {
    if (!file) {
      setPreview(null)
      return undefined
    }
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  const pick = (f) => {
    if (!f) return
    const problem = checkImage(f)
    setError(problem)
    onChange(problem ? null : f)
  }

  return (
    <div>
      <div
        className={`dropzone ${drag ? 'drag' : ''} ${preview ? 'has-image' : ''}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]) }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
      >
        {preview ? (
          <img src={preview} alt="Selected upload preview" />
        ) : (
          <div className="dropzone-empty">
            <div className="dz-icon">⬆</div>
            <strong>{label}{optional && ' (optional)'}</strong>
            <span className="muted small">Drag & drop or click · JPG, PNG, WEBP · max {MAX_IMAGE_MB} MB</span>
          </div>
        )}
        <input ref={input} type="file" accept="image/*" hidden onChange={(e) => { pick(e.target.files?.[0]); e.target.value = '' }} />
      </div>
      {file && (
        <div className="dz-footer">
          <span className="small muted">{file.name} · {(file.size / 1024).toFixed(0)} KB</span>
          <button type="button" className="link-btn" onClick={() => { onChange(null); setError(null) }}>Remove</button>
        </div>
      )}
      {error && <div className="field-error">{error}</div>}
    </div>
  )
}
