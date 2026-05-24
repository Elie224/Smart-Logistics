import { useState, useEffect, useCallback } from 'react'

/**
 * Generic data-fetching hook.
 * @param {string} path  — e.g. "/kpis"   (prefixed with /api/v1 internally)
 * @param {number} refreshMs — auto-refresh interval in ms, 0 = no refresh
 */
export function useApi(path, refreshMs = 0) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const r = await fetch(`/api/v1${path}`)
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
      setData(await r.json())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => {
    load()
    if (refreshMs > 0) {
      const id = setInterval(load, refreshMs)
      return () => clearInterval(id)
    }
  }, [load, refreshMs])

  return { data, loading, error, refresh: load }
}
