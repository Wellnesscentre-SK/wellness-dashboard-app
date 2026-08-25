import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import client, { apiError } from '../api/client'
import { Card, Kpi, Spinner } from '../components/ui'
import { InsightBullets, MiniKpi } from '../components/AiInsights'
import { CONCERN_LABELS, MODE_LABELS, REFERRAL_LABELS, STAKEHOLDER_LABELS } from '../utils/stats'

const number = new Intl.NumberFormat('en-IN')

const PIE_COLORS = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#0ea5e9', '#f43f5e', '#14b8a6', '#64748b']

function toChart(items, labels) {
  return (items || []).map(([key, value, pct]) => ({ key, name: (labels && labels[key]) || key, value, pct }))
}

function MetricBars({ data, color = '#253b7a' }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data.slice(0, 9)} layout="vertical" margin={{ left: 40 }}>
        <CartesianGrid stroke="#e5e7eb" horizontal={false} />
        <XAxis type="number" allowDecimals={false} />
        <YAxis dataKey="name" type="category" width={150} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="value" fill={color} radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function Insights() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    client
      .get('/insights')
      .then(({ data }) => setData(data))
      .catch((e) => setError(apiError(e)))
  }, [])

  const trend = useMemo(() => data?.trend || [], [data])
  const summary = data?.summary

  if (error) return <div className="text-sm text-red-600">{error}</div>
  if (!data) return <Spinner label="Running AI-style analysis…" />

  const concernData = toChart(data.aggregates.concern, CONCERN_LABELS)
  const stakeData = toChart(data.aggregates.stakeholder, STAKEHOLDER_LABELS)
  const referralData = toChart(data.aggregates.referral, REFERRAL_LABELS)
  const modeData = toChart(data.aggregates.mode, MODE_LABELS)
  const verticalData = toChart(data.aggregates.vertical, { WC: 'Wellness Centre', TA: 'Team A', YD: 'Your Dost', MW: 'Myndwell' })
  const topConcern = data.top.concern
  const topVertical = data.top.vertical

  return (
    <div className="space-y-6">
      <header className="report-header">
        <div>
          <p className="eyebrow">Wellness Centre / AI analytics</p>
          <h1>AI data insights</h1>
          <p className="header-subtitle">Automated analysis across all reporting periods — trends, outliers and the stories in your numbers.</p>
        </div>
        <div className="report-actions">
          <div className="period-select">
            <span>Coverage</span>
            <select className="min-w-0" value="" onChange={() => {}}>
              <option>{summary.period_count} reporting periods</option>
            </select>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        <Kpi label="Total cases" value={number.format(summary.total_cases)} accent="text-indigo-950" sub={`across ${summary.period_count} periods`} />
        <Kpi label="New cases" value={number.format(summary.total_new)} accent="text-sky-700" sub={`avg ${number.format(Math.round(summary.avg_new))}/period`} />
        <Kpi label="Follow-up" value={number.format(summary.total_followup)} accent="text-teal-700" sub={`avg ${number.format(Math.round(summary.avg_followup))}/period`} />
        <Kpi label="Sessions" value={number.format(summary.total_sessions)} accent="text-amber-700" sub={`avg ${number.format(Math.round(summary.avg_sessions))}/period`} />
        <Kpi label="Avg cases / period" value={number.format(Math.round(summary.avg_total))} accent="text-coral-700" sub="across all periods" />
        <Kpi label="Peak period" value={number.format(summary.best_period.total)} accent="text-emerald-700" sub={summary.best_period.label} />
      </section>

      <Card title="AI narrative" subtitle="Key findings generated from the data">
        <InsightBullets insights={data.insights} />
      </Card>

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card title="Case volume trend" subtitle="Total, new and follow-up cases per period" className="xl:col-span-2">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={trend} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid stroke="#e5e7eb" vertical={false} />
              <XAxis dataKey="short_label" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip labelFormatter={(label, payload) => payload?.[0]?.payload?.label || label} />
              <Legend />
              <Bar dataKey="new" name="New" fill="#387ca5" radius={[3, 3, 0, 0]} />
              <Bar dataKey="followup" name="Follow-up" fill="#2d918b" radius={[3, 3, 0, 0]} />
              <Line dataKey="total" name="Total" stroke="#172554" strokeWidth={2.5} dot={{ r: 3, fill: '#172554' }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Anomaly scan" subtitle="Periods that deviate from the average">
          {data.anomalies.length === 0 ? (
            <div className="flex h-[280px] flex-col items-center justify-center gap-2 text-center">
              <div className="text-3xl">✓</div>
              <p className="text-sm text-slate-500">No significant outliers detected across the reporting periods.</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {data.anomalies.map((a) => (
                <li key={a.period_id} className={`rounded-lg border px-3 py-2.5 text-sm ${a.kind === 'spike' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-red-200 bg-red-50 text-red-800'}`}>
                  <div className="font-semibold">{a.label}</div>
                  <div className="mt-0.5 text-xs opacity-80">
                    {a.kind === 'spike' ? 'Spike' : 'Dip'} of {number.format(Math.abs(a.deviation))} cases vs the {number.format(Math.round(a.average))} average.
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Dominant vertical" subtitle="Where case load concentrates">
          {topVertical ? (
            <div className="flex items-center gap-4">
              <ResponsiveContainer width="55%" height={240}>
                <PieChart>
                  <Pie data={verticalData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3}>
                    {verticalData.map((entry, index) => (
                      <Cell key={entry.key} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex-1 space-y-3">
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Top vertical</div>
                    <div className="text-2xl font-bold text-slate-900">{(topVertical && ({ WC: 'Wellness Centre', TA: 'Team A', YD: 'Your Dost', MW: 'Myndwell' }[topVertical[0]] || topVertical[0])) || '—'}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500">Share</div>
                  <div className="text-2xl font-bold text-emerald-700">{topVertical?.[2]}%</div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No vertical data yet.</p>
          )}
        </Card>

        <Card title="Concern profile" subtitle="Most frequently addressed concerns">
          <MetricBars data={concernData} color="#253b7a" />
        </Card>

        <Card title="Stakeholder profile" subtitle="Who is using the service">
          <MetricBars data={stakeData} color="#3aa6a0" />
        </Card>

        <Card title="Referral pathways">
          <MetricBars data={referralData} color="#d78051" />
        </Card>

        <Card title="Session mode">
          <MetricBars data={modeData} color="#5ba9d6" />
        </Card>

        <Card title="Summary stats">
          <div className="grid grid-cols-2 gap-3">
            <MiniKpi label="Top concern" value={topConcern?.[1] || 0} sub={topConcern ? (CONCERN_LABELS[topConcern[0]] || topConcern[0]) : '—'} />
            <MiniKpi label="Concern share" value={`${topConcern?.[2] || 0}%`} sub="of all reported concerns" />
            <MiniKpi label="Peak period" value={summary.best_period.total} sub={summary.best_period.label} />
            <MiniKpi label="Lowest period" value={summary.worst_period.total} sub={summary.worst_period.label} />
          </div>
        </Card>
      </section>
    </div>
  )
}
