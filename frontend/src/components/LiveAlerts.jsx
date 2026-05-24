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
    <div style={{
      display: 'flex', alignItems: 'center', gap: '10px',
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: '8px',
      padding: '10px 14px',
      boxShadow: '0 4px 20px rgba(0,0,0,0.45)',
      maxWidth: '340px',
      animation: 'slideInAlert 0.22s ease',
    }}>
      <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>{alert.icon}</span>
      <span style={{
        color: c.text, fontSize: '0.79rem', fontWeight: 500,
        flex: 1, lineHeight: 1.45,
      }}>
        {alert.message}
      </span>
      <button
        onClick={() => onDismiss(alert.id)}
        style={{
          background: 'none', border: 'none', color: '#64748b',
          cursor: 'pointer', fontSize: '1.1rem', padding: '0 2px',
          flexShrink: 0, lineHeight: 1,
        }}
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
    <div style={{
      position: 'fixed', bottom: '24px', right: '24px',
      display: 'flex', flexDirection: 'column-reverse', gap: '8px',
      zIndex: 9999, pointerEvents: 'none',
    }}>
      {alerts.slice(0, 5).map((a) => (
        <div key={a.id} style={{ pointerEvents: 'auto' }}>
          <AlertToast alert={a} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  )
}
