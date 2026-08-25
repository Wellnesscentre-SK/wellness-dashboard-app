import { useEffect, useState } from 'react'
import client, { apiError } from '../api/client'
import { Card, Spinner } from './ui'

const number = new Intl.NumberFormat('en-IN')

const TONE_STYLES = {
  info: 'border-sky-200 bg-sky-50 text-sky-800',
  positive: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  negative: 'border-red-200 bg-red-50 text-red-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
}
const TONE_DOT = {
  info: 'bg-sky-500',
  positive: 'bg-emerald-500',
  negative: 'bg-red-500',
  warning: 'bg-amber-500',
}

export function InsightBullets({ insights, limit = 10 }) {
  if (!insights?.length) {
    return <p className="text-sm text-slate-500">No insights available yet.</p>
  }
  const items = limit ? insights.slice(0, limit) : insights
  return (
    <ul className="space-y-2">
      {items.map((b, i) => (
        <li
          key={i}
          className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 text-sm ${TONE_STYLES[b.tone] || TONE_STYLES.info}`}
        >
          <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${TONE_DOT[b.tone] || TONE_DOT.info}`} />
          <span>{b.text}</span>
        </li>
      ))}
    </ul>
  )
}

export function MiniKpi({ label, value, sub, accent = 'text-slate-900' }) {
  const display = typeof value === 'string' ? value : number.format(value || 0)
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-0.5 text-xl font-bold ${accent}`}>{display}</div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>}
    </div>
  )
}

function fmtDelta(n) {
  if (n === undefined || n === null) return ''
  return `${n >= 0 ? '▲' : '▼'} ${n >= 0 ? '+' : ''}${number.format(n)} vs prev`
}
export function PeriodInsights({ periodId, title = 'AI Insights', className = '' }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!periodId) {
      setData(null)
      return
    }
    let alive = true
    setError('')
    setData(null)
    client
      .get(`/insights/${periodId}`)
      .then(({ data }) => alive && setData(data))
      .catch((e) => alive && setError(apiError(e)))
    return () => {
      alive = false
    }
  }, [periodId])

  if (!periodId) return null
  if (error) {
    return (
      <Card title={title} className={className}>
        <p className="text-sm text-red-600">{error}</p>
      </Card>
    )
  }
  if (!data) {
    return (
      <Card title={title} className={className}>
        <Spinner label="Analysing this period…" />
      </Card>
    )
  }

  const cmp = data.comparison
  return (
    <Card title={title} subtitle={data.period.label} className={className}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        <MiniKpi label="Total cases" value={data.totals.total} sub={cmp ? fmtDelta(cmp.delta_total) : undefined} />
        <MiniKpi label="New" value={data.totals.new} sub={cmp ? fmtDelta(cmp.delta_new) : undefined} />
        <MiniKpi label="Follow-up" value={data.totals.followup} sub={cmp ? fmtDelta(cmp.delta_followup) : undefined} />
        <MiniKpi label="Sessions" value={data.secondary.total_sessions} sub={cmp ? fmtDelta(cmp.delta_sessions) : undefined} />
        <MiniKpi label="Active cases" value={data.secondary.active_cases} />
      </div>
      <div className="mt-4">
        <InsightBullets insights={data.insights} limit={8} />
      </div>
    </Card>
  )
}
