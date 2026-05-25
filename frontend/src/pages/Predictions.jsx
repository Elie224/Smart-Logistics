import { useApi } from '../api.js'

const RISK_BADGE = {
  HIGH:    { cls: 'badge-red',    label: '🔴 ÉLEVÉ' },
  MEDIUM:  { cls: 'badge-orange', label: '🟠 MOYEN' },
  LOW:     { cls: 'badge-green',  label: '🟢 FAIBLE' },
  UNKNOWN: { cls: 'badge-grey',   label: '⚪ INCONNU' },
}

const FEATURE_LABELS = {
  wind_speed:          'Vitesse du vent',
  traffic_delay_s:     'Retard trafic',
  temperature:         'Température',
  route_duration_s:    'Durée du trajet',
  departure_month:     'Mois de départ',
  hour_cos:            'Heure (cos)',
  departure_hour:      'Heure de départ',
  hour_sin:            'Heure (sin)',
  departure_dow:       'Jour de la semaine',
  dow_cos:             'Jour (cos)',
  month_sin:           'Mois (sin)',
  transit_disruptions: 'Perturbations TC',
  dow_sin:             'Jour (sin)',
  month_cos:           'Mois (cos)',
  is_rush_hour:        'Heure de pointe',
  transit_status_enc:  'Statut réseau TC',
  transit_blocking:    'TC bloquantes',
  is_night:            'Départ nocturne',
  temp_below_5:        'Temp. < 5°C',
  traffic_high:        'Trafic élevé',
  is_weekend:          'Week-end',
}

const BAR_COLOR = { HIGH: '#ef4444', MEDIUM: '#f97316', LOW: '#22c55e', UNKNOWN: '#64748b' }

function fmtPct(p) { return p != null ? `${Math.round(p * 100)}%` : '—' }
function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}
function fmtFixed(v, digits = 3) {
  return Number.isFinite(v) ? Number(v).toFixed(digits) : '—'
}

// ── Model info panel ──────────────────────────────────────────────────────
function ModelInfo({ meta }) {
  if (!meta || meta.status === 'not_trained') return (
    <div className="state-box" style={{ marginBottom: 24 }}>
      ⏳ Modèle pas encore entraîné — le trainer démarrera sous peu.
    </div>
  )

  // Support les deux formats : feature_importances (GBT) ou coefficients (LogReg)
  const importanceMap = meta.feature_importances ?? meta.coefficients ?? {}
  const hasImportance = Object.keys(importanceMap).length > 0
  const isGBT  = !!meta.feature_importances
  const totalGBT = isGBT ? Math.max(Object.values(importanceMap).reduce((s, v) => s + Math.abs(v), 0), 0.001) : 1
  const maxVal = isGBT
    ? Math.max(...Object.values(importanceMap).map(v => Math.abs(v) / totalGBT), 0.001)
    : Math.max(...Object.values(importanceMap).map(Math.abs), 0.001)

  const nReal = meta.n_real ?? 0
  const nSynthetic = meta.n_synthetic ?? 0
  const nTotal = meta.n_total ?? (nReal + nSynthetic)
  const delayedPct = Number.isFinite(meta.delayed_pct) ? `${meta.delayed_pct.toFixed(1)}%` : '—'
  const aucTrain = fmtFixed(meta.auc_train, 3)
  const attemptedOnly = meta.status === 'insufficient_real_data' || meta.status === 'not_trained'
  const modelLabel = meta.model_type ?? (attemptedOnly ? 'Non entraîné (mode réel strict)' : '—')
  const trainedAtLabel = attemptedOnly ? 'Dernière tentative auto' : 'Entraîné le'
  const aucCv = meta.cv_auc_mean != null
    ? `${fmtFixed(meta.cv_auc_mean, 3)} ± ${fmtFixed(meta.cv_auc_std ?? 0, 3)}`
    : aucTrain

  return (
    <div className="model-info-grid" style={{ marginBottom: 24 }}>
      <div className="chart-card">
        <div className="chart-title">ℹ️ Informations modèle</div>
        {meta.status === 'insufficient_real_data' && (
          <div style={{
            marginBottom: 12,
            padding: '10px 12px',
            borderRadius: 10,
            border: '1px solid rgba(234,88,12,0.35)',
            background: 'rgba(251,146,60,0.08)',
            color: '#9a3412',
            fontSize: '0.8rem',
            lineHeight: 1.4,
          }}>
            ⚠️ {meta.message ?? 'Données réelles insuffisantes pour entraîner le modèle.'}
          </div>
        )}
        <table style={{ width: '100%' }}>
          <tbody>
            {[
              ['Algorithme',    modelLabel],
              [trainedAtLabel,  meta.trained_at ? new Date(meta.trained_at).toLocaleString('fr-FR') : '—'],
              ['Échantillons',  `${nTotal.toLocaleString('fr-FR')} (${nReal} réels + ${nSynthetic} synthétiques)`],
              ['AUC CV (5-fold)', aucCv],
              ['AUC train',     aucTrain],
              ['% retards',     delayedPct],
            ].map(([k, v]) => (
              <tr key={k} style={{ borderBottom: '1px solid rgba(51,65,85,0.4)' }}>
                <td style={{ padding: '8px 0', fontSize: '0.78rem', color: 'var(--muted)', width: '45%' }}>{k}</td>
                <td style={{ padding: '8px 0', fontSize: '0.82rem', fontWeight: 600 }}>{v ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="chart-card">
        <div className="chart-title">📊 Importance des features</div>
        <div className="coeff-list">
          {!hasImportance && (
            <div style={{ fontSize: '0.8rem', color: 'var(--muted)', lineHeight: 1.5 }}>
              Pas encore de poids de features exploitables.<br />
              Ils s'afficheront automatiquement dès qu'un modèle entraîné sur assez de données réelles sera disponible.
            </div>
          )}
          {Object.entries(importanceMap)
            .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
            .map(([name, val]) => {
              const normVal = isGBT ? Math.abs(val) / totalGBT : Math.abs(val)
              const pct   = normVal / maxVal * 100
              const color = isGBT
                ? (pct > 66 ? '#ef4444' : pct > 33 ? '#f97316' : '#6366f1')
                : (val > 0 ? '#ef4444' : '#22c55e')
              const label = isGBT
                ? `${(normVal * 100).toFixed(1)}%`
                : `${val > 0 ? '+' : ''}${val.toFixed(3)}`
              return (
                <div className="coeff-row" key={name}>
                  <span className="coeff-name">{FEATURE_LABELS[name] ?? name}</span>
                  <div className="coeff-track">
                    <div className="coeff-fill" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <span className="coeff-val" style={{ color }}>{label}</span>
                </div>
              )
            })}
        </div>
      </div>
    </div>
  )
}

// ── Risk card ─────────────────────────────────────────────────────────────
function RiskCard({ r }) {
  const badge = RISK_BADGE[r.risk_level] ?? RISK_BADGE.UNKNOWN
  const barColor = BAR_COLOR[r.risk_level] ?? '#64748b'
  const prob = r.delay_probability != null ? r.delay_probability * 100 : null
  const contextLabel = r.context_city
    ? `Zone trafic: ${r.context_city}`
    : `${r.origin} → ${r.destination}`

  return (
    <div className="risk-card">
      <div className="risk-card-header">
        <span className="risk-ref">{r.reference}</span>
        <span className={`badge ${badge.cls}`}>{badge.label}</span>
      </div>
      <div className="risk-route">{contextLabel}</div>

      {prob != null && (
        <>
          <div className="prob-bar-track">
            <div className="prob-bar-fill" style={{ width: `${prob.toFixed(0)}%`, background: barColor }} />
          </div>
          <div className="prob-label">Probabilité de retard : {fmtPct(r.delay_probability)}</div>
        </>
      )}

      {r.risk_factors?.length > 0 && (
        <div className="risk-factors">
          {r.risk_factors.map(f => <span key={f} className="risk-factor">{f}</span>)}
        </div>
      )}

      <div className="risk-reco">{r.recommendation}</div>
      <div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginTop: 8 }}>
        Arrivée prévue : {fmtDate(r.expected_arrival_time)}
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────
export default function Predictions() {
  const { data: risks,  loading: lr, refresh } = useApi('/predictions/ml-delay-risk',  20_000)
  const { data: meta,   loading: lm }          = useApi('/predictions/ml-model-info',  120_000)

  if ((lr || lm) && !risks) return <div className="state-box">Chargement…</div>

  return (
    <div className="page-body">
      <div className="toolbar-end">
        <button className="refresh-btn" onClick={refresh}>⟳ Actualiser</button>
      </div>

      <ModelInfo meta={meta} />

      <div style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: 12, color: 'var(--text)' }}>
        Livraisons actives ({risks?.length ?? 0})
      </div>

      {risks?.length === 0 && (
        <div className="state-box">Aucune livraison active.</div>
      )}

      <div className="risk-grid">
        {risks?.map(r => <RiskCard key={r.delivery_id} r={r} />)}
      </div>
    </div>
  )
}
