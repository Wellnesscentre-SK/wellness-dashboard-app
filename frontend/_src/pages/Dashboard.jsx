import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import client, { apiError, generateReport } from '../api/client'
import { Card, Kpi, Spinner, StatusBadge } from '../components/ui'
import { PeriodInsights } from '../components/AiInsights'
import { computeStats, CONCERN_LABELS, MODE_LABELS, REFERRAL_LABELS, STAKEHOLDER_LABELS } from '../utils/stats'

const PROVIDERS = ['WLN Ctr', 'Team A', 'Your Dost', 'Myndwell']
const providerColors = { 'WLN Ctr': '#253b7a', 'Team A': '#3aa6a0', 'Your Dost': '#5ba9d6', Myndwell: '#e7a34b' }
const number = new Intl.NumberFormat('en-IN')
const sum = (items, key) => items.reduce((total, item) => total + (Number(item[key]) || 0), 0)

function chartData(values, labels) {
  return Object.entries(values).filter(([, value]) => value > 0).map(([name, value]) => ({ name, label: labels[name] || name, value })).sort((a, b) => b.value - a.value)
}

function comparison(current, previous) {
  if (previous === undefined || previous === null) return 'No earlier period'
  const delta = current - previous
  return `${delta >= 0 ? '+' : ''}${number.format(delta)} vs previous period`
}

function inclusiveDays(period) {
  return Math.round((Date.parse(`${period.period_end}T00:00:00Z`) - Date.parse(`${period.period_start}T00:00:00Z`)) / 86400000) + 1
}

function priorCoverage(current, previous, periods) {
  if (current.report_type !== 'weekly') return { state: 'not-weekly', label: 'Monthly reports are not compared week to week.' }
  const overlapping = periods.some((period) => period.id !== current.id && period.report_type === 'weekly' && period.period_start <= current.period_end && period.period_end >= current.period_start)
  if (overlapping) return { state: 'overlap', label: 'Overlapping weekly coverage detected; compare with care.' }
  if (!previous) return { state: 'unavailable', label: 'No earlier weekly period is available.' }
  const nextDay = new Date(`${previous.period_end}T00:00:00Z`)
  nextDay.setUTCDate(nextDay.getUTCDate() + 1)
  if (nextDay.toISOString().slice(0, 10) !== current.period_start) return { state: 'gap', label: 'Gap between periods — comparison is retained and flagged.' }
  if (inclusiveDays(current) !== 7 || inclusiveDays(previous) !== 7) return { state: 'partial', label: 'Non-standard weekly coverage — comparison is retained and flagged.' }
  return { state: 'adjacent', label: 'Adjacent full-week coverage.' }
}

export default function Dashboard() {
  const [periods, setPeriods] = useState([])
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    client.get('/periods').then(({ data }) => { setPeriods(data); if (data[0]) setSelected(String(data[0].id)) }).catch((e) => setError(apiError(e))).finally(() => setLoading(false))
  }, [])
  const current = useMemo(() => periods.find((p) => String(p.id) === selected), [periods, selected])
  const previous = useMemo(() => current?.report_type === 'weekly' && periods.filter((p) => p.report_type === 'weekly' && p.period_end < current.period_start).sort((a, b) => b.period_end.localeCompare(a.period_end))[0], [periods, current])
  const coverage = useMemo(() => current ? priorCoverage(current, previous, periods) : null, [current, previous, periods])
  const stats = useMemo(() => current ? computeStats(current.case_rows) : null, [current])
  const previousStats = useMemo(() => previous ? computeStats(previous.case_rows) : null, [previous])
  const operations = useMemo(() => (current?.secondary_metrics || []).find((row) => row.vertical === 'Total') || {}, [current])

  if (loading) return <Spinner label="Loading reporting console..." />
  if (error) return <div className="report-alert error">{error}</div>
  if (!current) return <Card title="No reports available"><p className="text-sm text-slate-600">Import a weekly or monthly Excel report to begin reporting.</p></Card>

  const providerRows = ['new', 'followup'].map((caseType) => {
    const rows = current.raw_rows?.filter((row) => row.case_type === caseType) || []
    const data = Object.fromEntries(PROVIDERS.map((provider) => [provider, rows.find((row) => row.sub_team === provider)?.raw_payload?.total_cases || 0]))
    return { caseType, ...data, total: sum(Object.entries(data).map(([provider, total_cases]) => ({ provider, total_cases })), 'total_cases') }
  })
  const totalCases = stats.new.total + stats.followup.total
  const grandRow = Object.fromEntries(PROVIDERS.map((provider) => [provider, providerRows[0][provider] + providerRows[1][provider]]))
  const totalsReconcile = providerRows[0].total === stats.new.total && providerRows[1].total === stats.followup.total
  const verticalData = PROVIDERS.map((provider) => ({ provider, New: providerRows[0][provider], 'Follow-up': providerRows[1][provider] }))
  const gender = [{ name: 'Male', value: stats.gender.m }, { name: 'Female', value: stats.gender.f }, { name: 'Other / not stated', value: stats.gender.o }]

  const exportPpt = async () => { setExporting(true); try { await generateReport(current.id, 'ppt', previous?.id) } catch (e) { setError(apiError(e)) } finally { setExporting(false) } }
  const go = (step) => { const index = periods.findIndex((p) => p.id === current.id); const next = periods[index + step]; if (next) setSelected(String(next.id)) }

  return <div className="report-console space-y-6">
    <header className="report-header">
      <div>
        <p className="eyebrow">Wellness Centre / institutional reporting</p>
        <h1>Operations overview</h1>
        <p className="header-subtitle">A transparent view of cases, care pathways and reporting quality.</p>
      </div>
      <div className="report-actions">
        <button className="period-arrow" onClick={() => go(1)} disabled={!periods[periods.findIndex((p) => p.id === current.id) + 1]} aria-label="Previous report">←</button>
        <label className="period-select"><span>Reporting period</span><select value={selected} onChange={(e) => setSelected(e.target.value)}>{periods.map((p) => <option key={p.id} value={p.id}>{p.report_type} · {p.period_start} — {p.period_end}</option>)}</select></label>
        <button className="period-arrow" onClick={() => go(-1)} disabled={!periods[periods.findIndex((p) => p.id === current.id) - 1]} aria-label="Next report">→</button>
        <button className="export-button" onClick={exportPpt} disabled={exporting}>{exporting ? 'Preparing...' : 'Export PPT'}</button>
      </div>
    </header>

    <section className={`audit-ribbon ${totalsReconcile && !stats.needsReview ? 'is-clear' : 'is-warning'}`}>
      <div><span className="audit-label">Report period</span><strong>{current.period_start} — {current.period_end}</strong><small>{current.report_type} report · source: {current.source}</small></div>
      <div><span className="audit-label">Audit state</span><StatusBadge status={current.status} /><small>{totalsReconcile ? 'Provider totals reconcile with report totals.' : 'Provider totals require review.'}</small></div>
      <div><span className="audit-label">Prior period coverage</span><strong>{previous ? `${previous.period_start} — ${previous.period_end}` : 'Not available'}</strong><small><b className={`coverage-state ${coverage.state}`}>{coverage.state.replace('-', ' ')}</b> {coverage.label}</small></div>
    </section>

    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
      <Kpi label="Total cases" value={number.format(totalCases)} accent="text-indigo-950" sub={comparison(totalCases, previousStats && previousStats.new.total + previousStats.followup.total)} />
      <Kpi label="New cases" value={number.format(stats.new.total)} accent="text-sky-700" sub={comparison(stats.new.total, previousStats?.new.total)} />
      <Kpi label="Follow-up" value={number.format(stats.followup.total)} accent="text-teal-700" sub={comparison(stats.followup.total, previousStats?.followup.total)} />
      <Kpi label="Total sessions" value={number.format(operations.total_sessions || 0)} accent="text-amber-700" sub="All reporting providers" />
      <Kpi label="Active cases" value={number.format(operations.active_cases || 0)} accent="text-coral-700" sub="Active as of report date" />
    </section>

    <section className="formula-flow" aria-label="Case total calculation">
      <div className="flow-heading"><div><p className="eyebrow">Calculation trace</p><h2>How the headline total is formed</h2></div><span className={totalsReconcile ? 'validation-pass' : 'validation-review'}>{totalsReconcile ? '✓ Reconciled' : '! Review required'}</span></div>
      <div className="flow-steps"><div className="flow-node provider-node"><span>Provider inputs</span><strong>{PROVIDERS.length} teams</strong><small>WLN Ctr · Team A · Your Dost · Myndwell</small></div><span className="flow-arrow">→</span><div className="flow-node new-node"><span>New cases</span><strong>{number.format(stats.new.total)}</strong><small>Σ provider new entries</small></div><span className="flow-plus">+</span><div className="flow-node follow-node"><span>Follow-up</span><strong>{number.format(stats.followup.total)}</strong><small>Σ provider follow-ups</small></div><span className="flow-arrow">→</span><div className="flow-node total-node"><span>Grand total</span><strong>{number.format(totalCases)}</strong><small>{stats.new.total} + {stats.followup.total}</small></div></div>
    </section>

    <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <Card title="Provider case mix" subtitle="New and follow-up cases, by source provider" className="xl:col-span-2"><ResponsiveContainer width="100%" height={290}><BarChart data={verticalData}><CartesianGrid stroke="#e5e7eb" vertical={false}/><XAxis dataKey="provider" tick={{fontSize:12}}/><YAxis allowDecimals={false}/><Tooltip/><Legend/><Bar dataKey="New" fill="#387ca5" radius={[3,3,0,0]}/><Bar dataKey="Follow-up" fill="#2d918b" radius={[3,3,0,0]}/></BarChart></ResponsiveContainer></Card>
      <Card title="Gender" subtitle="Reported distribution"><ResponsiveContainer width="100%" height={290}><PieChart><Pie data={gender} dataKey="value" nameKey="name" innerRadius={64} outerRadius={103} paddingAngle={3}>{gender.map((entry, index) => <Cell key={entry.name} fill={['#253b7a','#3aa6a0','#e7a34b'][index]}/>)}</Pie><Tooltip/><Legend/></PieChart></ResponsiveContainer></Card>
    </section>

    <Card title="Provider reconciliation" subtitle="Every subtotal is the sum of its source-provider values."><div className="overflow-x-auto"><table className="report-table"><thead><tr><th>Case group</th>{PROVIDERS.map((p) => <th key={p}><i style={{background: providerColors[p]}} />{p}</th>)}<th>Formula total</th></tr></thead><tbody>{providerRows.map((row) => <tr key={row.caseType}><th>{row.caseType === 'new' ? 'New cases' : 'Follow-up cases'}</th>{PROVIDERS.map((p) => <td key={p}>{number.format(row[p])}</td>)}<td><strong>{number.format(row.total)}</strong></td></tr>)}<tr className="grand-row"><th>Grand total</th>{PROVIDERS.map((p) => <td key={p}>{number.format(grandRow[p])}</td>)}<td><strong>{number.format(totalCases)}</strong></td></tr></tbody></table></div></Card>

    <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card title="Concern areas" subtitle="Counts may overlap; they are not used to calculate total cases."><MetricBars data={chartData(stats.concerns, CONCERN_LABELS)} color="#253b7a" /></Card>
      <Card title="Stakeholder groups" subtitle="Counts may overlap; they are not used to calculate total cases."><MetricBars data={chartData(stats.stakeholders, STAKEHOLDER_LABELS)} color="#3aa6a0" /></Card>
      <Card title="Referral pathways"><MetricBars data={chartData(stats.referral, REFERRAL_LABELS)} color="#d78051" /></Card>
      <Card title="Session mode"><MetricBars data={chartData(stats.modes, MODE_LABELS)} color="#5ba9d6" /></Card>
    </section>

    <section className="grid grid-cols-1 lg:grid-cols-2 gap-6"><Card title="Operational signals" subtitle="Connected metrics from the secondary report block"><div className="operation-grid">{[['Early prevention warnings', operations.early_prevention_warning], ['Did not turn up', operations.no_show_turn_up], ['Active cases', operations.active_cases], ['More than 4 sessions', operations.clients_over_4_sessions]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{number.format(value || 0)}</strong></div>)}</div></Card><Card title="Enquiry mode" subtitle="How people reached the service"><div className="operation-grid">{[['Email', current.enquiry_modes?.mail], ['Calls received', current.enquiry_modes?.calls_recd], ['Outgoing calls', current.enquiry_modes?.calls_out]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{number.format(value || 0)}</strong></div>)}</div></Card></section>

    <PeriodInsights periodId={current.id} title="AI Insights — this period" />
  </div>
}

function MetricBars({ data, color }) { return <ResponsiveContainer width="100%" height={270}><BarChart data={data.slice(0, 9)} layout="vertical" margin={{left: 35}}><CartesianGrid stroke="#e5e7eb" horizontal={false}/><XAxis type="number" allowDecimals={false}/><YAxis dataKey="label" type="category" width={120} tick={{fontSize:11}}/><Tooltip/><Bar dataKey="value" fill={color} radius={[0,3,3,0]}/></BarChart></ResponsiveContainer> }
