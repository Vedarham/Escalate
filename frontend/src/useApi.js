import { useCallback, useRef, useState } from 'react'

/** Wraps an API call with loading / error / result state and ignores stale responses. */
export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const seq = useRef(0)

  const run = useCallback(async (fn) => {
    const id = ++seq.current
    setLoading(true)
    setError(null)
    try {
      const res = await fn()
      if (id === seq.current) setResult(res)
      return res
    } catch (e) {
      if (id === seq.current) setError(e)
      return null
    } finally {
      if (id === seq.current) setLoading(false)
    }
  }, [])

  return { loading, error, result, run, setError, setResult }
}
