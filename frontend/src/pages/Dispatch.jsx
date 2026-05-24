import { useApi } from '../api.js'

// Couleurs officielles par ligne
const LINE_COLOR = {
  'M1': '#FFCE00', 'M4': '#9B1B80', 'M6': '#82BE00', 'M13': '#4DB848', 'M14': '#6B267E',
  'RER A': '#FF1400', 'RER B': '#3C91DC', 'RER C': '#FECE00', 'RER D': '#00814F', 'RER E': '#C04191',
  'T3a': '#6E3219', 'T3b': '#A0522D',
  'Bus 38': '#F5A623', 'Bus 63': '#F5A623', 'Bus 95': '#F5A623',
  'Tram R': '#8B4513',
  'L1': '#00A651', 'L3': '#0072BC', 'L5': '#EE1C25',
}
// M1/M2 Lille ont la même clé que Paris — on dinstingue par ville
const LINE_COLOR_LILLE = { 'M1': '#FF6600', 'M2': '#0099CC' }

const TYPE_ICON = { METRO: '🚇', RER: '🚆', TRAM: '🚋', BUS: '🚌', TRAIN: '🚄' }

const STATUS_LABEL = { NORMAL: 'Normal', REDUCED: 'Réduit', DISRUPTED: 'Perturbé' }
const STATUS_COLOR = { NORMAL: 'green', REDUCED: 'orange', DISRUPTED: 'red' }

function lineColor(city, name) {
  if (city === 'Lille' && LINE_COLOR_LILLE[name]) return LINE_COLOR_LILLE[name]
  return LINE_COLOR[name] ?? '#6366f1'
}

function LineTable({ lines, city }) {
  if (!lines.length) return null
  return (
    <div className="table-card" style={{ marginBottom: 16 }}>
      <div className="table-card-header">🗺 {city} — {lines.length} ligne(s)</div>
      <table>
        <thead>
          <tr>
            <th>Ligne</th>
            <th>Type</th>
            <th>Statut</th>
            <th>Incident / Info</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((row, i) => {
            const color  = lineColor(row.city, row.line_name)
            const status = row.network_status ?? 'NORMAL'
            const icon   = TYPE_ICON[row.line_type] ?? '🚌'
            return (
              <tr key={i}>
                <td>
                  <span style={{
                    display: 'inline-block', padding: '2px 12px', borderRadius: 5,
                    background: color, color: '#fff', fontWeight: 900,
                    fontSize: '0.75rem', minWidth: 36, textAlign: 'center',
                    textShadow: '0 1px 2px rgba(0,0,0,0.4)',
                  }}>
                    {row.line_name}
                  </span>
                </td>
                <td style={{ fontSize: '0.85rem' }}>{icon} {row.line_type}</td>
                <td>
                  <span className={`badge badge-${STATUS_COLOR[status] ?? 'grey'}`}>
                    {STATUS_LABEL[status] ?? status}
                  </span>
                </td>
                <td style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                  {row.most_severe_message ?? '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Dispatch() {
  const { data, loading, error, refresh } = useApi('/transit/lines', 60_000)

  if (loading && !data) return <div className="state-box">Chargement…</div>
  if (error) return <div className="state-box" style={{ color: 'var(--red)' }}>Erreur : {error}</div>

  const rows  = data ?? []
  const paris = rows.filter(r => r.city === 'Paris')
  const lille = rows.filter(r => r.city === 'Lille')

  return (
    <div className="page-body">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <button className="refresh-btn" onClick={refresh}>⟳ Actualiser</button>
      </div>

      <LineTable lines={paris} city="Paris" />
      <LineTable lines={lille} city="Lille" />

      {!paris.length && !lille.length && (
        <div className="state-box">Aucune donnée de transit disponible.</div>
      )}
    </div>
  )
}
