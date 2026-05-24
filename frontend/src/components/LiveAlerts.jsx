import { useEffect } from 'react'

const COLORS = {
  critical: { bg: 'rgba(239,68,68,0.14)',  border: '#ef4444', text: '#fca5a5' },
  warning:  { bg: 'rgba(245,158,11,0.14)', border: '#f59e0b', text: '#fcd34d' },
  info:     { bg: 'rgba(34,197,94,0.12)',  border: '#22c55e', text: '#86efac' },
}

function AlertToast({ alert, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(alert.id), 7000)
    return () => clearTimeout(t)
  }, [alert.id, onDismiss])

  const c = COLORS[alert.level] ?? COLORS.info

  return (
    <div
      className="live-alert-toast"
      style={{ background: c.bg, border: `1px solid ${c.border}` }}
    >
      <span className="live-alert-icon">{alert.icon}</span>
      <span className="live-alert-message" style={{ color: c.text }}>
        {alert.message}
      </span>
      <button
        onClick={() => onDismiss(alert.id)}
        className="live-alert-close"
        aria-label="Fermer"
      >×</button>
    </div>
  )
}

/**
 * Conteneur de toasts en bas à droite de l'écran.
 */
export default function LiveAlerts({ alerts, onDismiss }) {
  if (!alerts.length) return null

  return (
    <div className="live-alerts">
      {alerts.slice(0, 5).map((a) => (
        <div key={a.id} className="live-alert-item">
          <AlertToast alert={a} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  )
}
