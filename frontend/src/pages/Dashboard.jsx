import { useApi } from '../api.js'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'

// ── Helpers ───────────────────────────────────────────────────────────────
const fmtNum = (n) => { if (n == null) return '—'; const num = Number(n); return isNaN(num) ? String(n) : num.toLocaleString('fr-FR') }
const fmtDec = (n, d = 1) => (n == null || isNaN(n) ? '—' : Number(n).toFixed(d))

// Chart colors — TC (clés = valeurs exactes retournées par l'API)
const TYPE_PIE_COLORS = { 'Métro': '#6366f1', 'RER': '#ef4444', 'Tramway': '#a78bfa', 'Bus': '#f59e0b', 'Train': '#3b82f6' }
const TYPE_ICON       = { 'Métro': '🚇', 'RER': '🚆', 'Tramway': '🚋', 'Bus': '🚌', 'Train': '🚄' }

// ── KPI Card ──────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, color = 'blue' }) {
  return (
    <div className={`kpi-card accent-${color}`}>
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value ${color}`}>{fmtNum(value)}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const { data: kpis }         = useApi('/kpis',              30_000)
  const { data: overview }     = useApi('/business/overview', 30_000)
  const { data: sources }      = useApi('/ingestion-status',  60_000)
  const { data: traffic }      = useApi('/traffic/latest',    60_000)
  const { data: transitLines } = useApi('/transit/lines',     60_000)

  // ── TC KPIs (temps réel depuis la DB)
  const tcTotal     = transitLines?.length ?? 0
  const tcNormal    = transitLines?.filter(l => l.network_status === 'NORMAL').length    ?? 0
  const tcReduced   = transitLines?.filter(l => l.network_status === 'REDUCED').length   ?? 0
  const tcDisrupted = transitLines?.filter(l => l.network_status === 'DISRUPTED').length ?? 0

  // ── Statut bar chart (Paris vs Lille, par statut)
  const statusBar = ['NORMAL', 'REDUCED', 'DISRUPTED'].map(st => ({
    name:  { NORMAL: 'Normal', REDUCED: 'Réduit', DISRUPTED: 'Perturbé' }[st],
    Paris: transitLines?.filter(l => l.city === 'Paris' && l.network_status === st).length ?? 0,
    Lille: transitLines?.filter(l => l.city === 'Lille' && l.network_status === st).length ?? 0,
  }))

  // ── Type pie chart
  const typeMap = {}
  transitLines?.forEach(l => { typeMap[l.line_type] = (typeMap[l.line_type] ?? 0) + 1 })
  const typePie = Object.entries(typeMap).map(([name, value]) => ({ name, value }))

  const avgDelayMin = Math.round((parseFloat(overview?.average_route_delay_seconds) || 0) / 60)

  if (!transitLines && !kpis) return <div className="state-box">Chargement des données…</div>

  return (
    <div className="page-body">

      {/* ── KPIs TC ── */}
      <div className="kpi-grid">
        <KpiCard label="Lignes TC total"   value={tcTotal}     color="blue"   sub="Paris &amp; Lille" />
        <KpiCard label="Trafic normal"     value={tcNormal}    color="green"  sub="lignes opérationnelles" />
        <KpiCard label="Service réduit"    value={tcReduced}   color="orange" sub="fréquences diminuées" />
        <KpiCard label="Perturbées"        value={tcDisrupted} color="red"    sub="incidents actifs" />
        <KpiCard label="Délai trafic moy." value={`${avgDelayMin} min`} color="orange" sub="Paris &amp; Lille" />
        <KpiCard label="Température moy."  value={`${fmtDec(parseFloat(overview?.average_temperature))}°C`} color="purple" sub="toutes villes" />
        <KpiCard label="Sources fraîches"  value={overview?.fresh_sources} color="green" sub={`${overview?.stale_sources ?? 0} périmées`} />
        <KpiCard label="Points GPS"        value={kpis?.total_gps_points}  color="blue"  sub="en base" />
      </div>

      {/* ── Graphiques TC ── */}
      <div className="charts-row">
        <div className="chart-card">
          <div className="chart-title">Statut des lignes TC</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={statusBar} barCategoryGap="35%">
              <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: '0.8rem' }} itemStyle={{ color: '#e2e8f0' }} />
              <Bar dataKey="Paris" fill="#6366f1" radius={[4, 4, 0, 0]} name="Paris" />
              <Bar dataKey="Lille" fill="#38bdf8" radius={[4, 4, 0, 0]} name="Lille" />
              <Legend iconType="circle" iconSize={8} formatter={(v) => <span style={{ color: '#94a3b8', fontSize: '0.78rem' }}>{v}</span>} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-card">
          <div className="chart-title">Répartition par type de TC</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={typePie} cx="40%" cy="50%"
                innerRadius={60} outerRadius={88}
                paddingAngle={4} dataKey="value"
                isAnimationActive={false}
              >
                {typePie.map((entry, i) => (
                  <Cell key={i} fill={TYPE_PIE_COLORS[entry.name] ?? '#64748b'} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: '0.82rem' }}
                itemStyle={{ color: '#e2e8f0' }}
                formatter={(value, name) => [`${value} ligne${value > 1 ? 's' : ''}`, `${TYPE_ICON[name] ?? '🚍'} ${name}`]}
              />
              <Legend
                layout="vertical" align="right" verticalAlign="middle"
                iconType="circle" iconSize={10}
                formatter={(name) => {
                  const entry = typePie.find(d => d.name === name)
                  return (
                    <span style={{ color: '#cbd5e1', fontSize: '0.8rem' }}>
                      {TYPE_ICON[name] ?? '🚍'} {name}
                      <span style={{ marginLeft: 6, fontWeight: 700, color: TYPE_PIE_COLORS[name] ?? '#64748b' }}>
                        {entry?.value}
                      </span>
                    </span>
                  )
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Trafic urbain ── */}
      {traffic && traffic.length > 0 && (
        <div className="table-card" style={{ marginBottom: 24 }}>
          <div className="table-card-header">Trafic urbain en temps réel</div>
          <div className="traffic-cities-row">
            {traffic.map(city => {
              const delayMin = Math.round((city.avg_delay_seconds || 0) / 60)
              const maxMin   = Math.round((city.max_delay_seconds  || 0) / 60)
              const statusColor = city.traffic_status === 'CONGESTED' ? '#ef4444' : city.traffic_status === 'SLOW' ? '#f97316' : '#22c55e'
              const statusLabel = city.traffic_status === 'CONGESTED' ? 'Congestionné' : city.traffic_status === 'SLOW' ? 'Ralenti' : 'Fluide'
              return (
                <div key={city.city} className="traffic-city-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <span style={{ fontWeight: 700, fontSize: '1rem' }}>{city.city}</span>
                    <span style={{ padding: '3px 12px', borderRadius: 999, fontSize: '0.75rem', fontWeight: 700, background: statusColor + '22', color: statusColor, border: `1px solid ${statusColor}55` }}>{statusLabel}</span>
                  </div>
                  <div className="traffic-kpis" style={{ marginBottom: 12 }}>
                    <div><div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginBottom: 2 }}>Retard moyen</div><div style={{ fontSize: '1.4rem', fontWeight: 700, color: statusColor }}>{delayMin} min</div></div>
                    <div><div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginBottom: 2 }}>Retard max</div><div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--muted)' }}>{maxMin} min</div></div>
                    <div><div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginBottom: 2 }}>Axes surveillés</div><div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{city.route_count}</div></div>
                  </div>
                  {city.routes && (
                    <div className="traffic-routes">
                      {city.routes.map(r => {
                        const rd = Math.round((r.delay_seconds || 0) / 60)
                        const rc = rd > 10 ? '#ef4444' : rd > 3 ? '#f97316' : '#22c55e'
                        return (
                          <div key={r.route_name} className="traffic-route-row">
                            <span className="traffic-route-name">{r.route_name.replace(`${city.city} - `, '')}</span>
                            <span style={{ color: rc, fontWeight: 600 }}>+{rd} min</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Réseau TC par ville ── */}
      {transitLines && transitLines.length > 0 && (() => {
        const byCity = {}
        transitLines.forEach(l => {
          if (!byCity[l.city]) byCity[l.city] = []
          byCity[l.city].push(l)
        })
        return (
          <div className="table-card" style={{ marginBottom: 24 }}>
            <div className="table-card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Réseau de transport en commun</span>
              <span style={{ fontSize: '0.72rem', color: '#475569', fontWeight: 400 }}>→ Voir détails dans <b style={{ color: '#6366f1' }}>Transports</b></span>
            </div>
            <div className="transit-cities-row">
              {Object.entries(byCity).map(([city, lines]) => {
                const disrupted = lines.filter(l => l.network_status === 'DISRUPTED').length
                const reduced   = lines.filter(l => l.network_status === 'REDUCED').length
                const normal    = lines.length - disrupted - reduced
                const stCol   = disrupted > 0 ? '#ef4444' : reduced > 0 ? '#f59e0b' : '#22c55e'
                const stLabel = disrupted > 0 ? 'Perturbations' : reduced > 0 ? 'Service réduit' : 'Trafic normal'
                return (
                  <div key={city} className="transit-city-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>{city}</span>
                      <span style={{ padding: '2px 10px', borderRadius: 999, fontSize: '0.7rem', fontWeight: 700, background: stCol + '18', color: stCol, border: `1px solid ${stCol}44` }}>{stLabel}</span>
                    </div>
                    <div className="transit-kpis">
                      <div><div style={{ fontSize: '0.65rem', color: '#64748b' }}>Lignes</div><div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{lines.length}</div></div>
                      {disrupted > 0 && <div><div style={{ fontSize: '0.65rem', color: '#64748b' }}>Perturbées</div><div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#ef4444' }}>{disrupted}</div></div>}
                      {reduced   > 0 && <div><div style={{ fontSize: '0.65rem', color: '#64748b' }}>Réduites</div><div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f59e0b' }}>{reduced}</div></div>}
                      <div><div style={{ fontSize: '0.65rem', color: '#64748b' }}>Normales</div><div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#22c55e' }}>{normal}</div></div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}

      {/* ── Sources de données ── */}
      {sources && (
        <div className="table-card">
          <div className="table-card-header">Sources de données</div>
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Dernier enregistrement</th>
                <th>Nb enregistrements</th>
                <th>Statut</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => {
                const fresh = s.status === 'fresh'
                return (
                  <tr key={s.source}>
                    <td style={{ fontWeight: 600 }}>{s.source}</td>
                    <td style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{s.last_record_at ? new Date(s.last_record_at).toLocaleString('fr-FR') : '—'}</td>
                    <td>{fmtNum(s.record_count)}</td>
                    <td><span className={`badge badge-${fresh ? 'green' : 'orange'}`}>{fresh ? '✓ Actif' : '⚠ Périmé'}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
