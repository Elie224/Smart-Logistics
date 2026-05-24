import { useEffect, useState, useRef, useCallback } from 'react'

/**
 * useWebSocket — connexion WebSocket avec reconnexion automatique.
 * @param {string} path  ex: '/api/v1/ws/live'
 * @returns {{ snapshot, alerts, connected, dismissAlert }}
 */
export function useWebSocket(path) {
  const [snapshot,  setSnapshot]  = useState(null)
  const [alerts,    setAlerts]    = useState([])
  const [connected, setConnected] = useState(false)

  const wsRef          = useRef(null)
  const reconnectTimer = useRef(null)
  const mountedRef     = useRef(true)
  const alertCounter   = useRef(0)

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    try {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const url   = `${proto}//${window.location.host}${path}`
      const ws    = new WebSocket(url)

      ws.onopen = () => {
        if (mountedRef.current) setConnected(true)
      }

      ws.onmessage = (e) => {
        if (!mountedRef.current) return
        try {
          const data = JSON.parse(e.data)
          if (data.snapshot) setSnapshot(data.snapshot)
          if (data.alerts?.length > 0) {
            const tagged = data.alerts.map((a) => ({
              ...a,
              id: `ws-${++alertCounter.current}`,
            }))
            setAlerts((prev) => [...tagged, ...prev].slice(0, 20))
          }
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setConnected(false)
        reconnectTimer.current = setTimeout(connect, 4000)
      }

      ws.onerror = () => ws.close()
      wsRef.current = ws
    } catch { /* ignore connection errors — will retry */ }
  }, [path])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const dismissAlert = useCallback((id) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id))
  }, [])

  return { snapshot, alerts, connected, dismissAlert }
}
