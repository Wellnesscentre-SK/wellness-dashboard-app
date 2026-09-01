import { useEffect, useMemo, useState } from 'react'
import client, { apiError } from '../api/client'
import { Card, ErrorBox, Spinner } from './ui'
import { InsightBullets } from './AiInsights'

const number = new Intl.NumberFormat('en-IN')

const COMPARE_TYPES = [
  { key: 'week', label: 'Week-over-Week', short: 'WoW', reportType: 'weekly', icon: '🗓️' },
  { key: 'month', label: 'Month-over-Month', short: 'MoM', reportType: 'monthly', icon: '📆' },
  { key: 'year', label: 'Year-over-Year', short: 'YoY', reportType: 'monthly', icon: '🌏' },
]

const GROUP_TITLES = {
  gender: 'Gender',
  mode: 'Mode of Session',
  referral: 'Referral Type',
  concern: 'Range of Concern',
  stakeholder: 'Stakeholder',
  vertical: 'Vertical',
}

function fmtPct(pct) {
  if (pct === null || pct === undefined) return '—'
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
}

function deltaColor(delta) {
  if (delta > 0) return 'text-emerald-600'
  if (delta < 0) return 'text-rose-600'
  return 'text-slate-400'
}

function DeltaKpi({ label, a, b, delta, pct }) {
  const up = delta > 0
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1.5">
        <span className="text-xl font-bold text-slate-900">{number.format(b || 0)}</span>
        <span className={`text-[11px] font-semibold ${deltaColor(delta)}`}>
          {up ? '▲' : delta < 0 ? '▼' : '•'} {delta >= 0 ? '+' : ''}
          {number.format(delta || 0)} ({fmtPct(pct)})
        </span>
      </div>
      <div className="mt-0.5 text-[11px] text-slate-500">
        Baseline {number.format(a || 0)} → Current
      </div>
    </div>
  )
}

function periodLabel(p) {
  if (!p) return ''
  return `${p.report_type === 'monthly' ? 'Monthly' : 'Weekly'} · ${p.period_start} → ${p.period_end}`
}

export default function CompareAnalysis() {
  const [periods, setPeriods] = useState([])
  const [type, setType] = useState('week')
  const [fromId, setFromId] = useState('')
  const [toId, setToId] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    client
      .get('/periods')
      .then(({ data }) => setPeriods(data))
      .catch((e) => setError(apiError(e)))
  }, [])

  const currentType = COMPARE_TYPES.find((t) => t.key === type) || COMPARE_TYPES[0]
  const typePeriods = usePeriodsOf(periods, currentType.reportType)

  // Auto-select the latest pair when periods or comparison type changes.
  useEffect(() => {
    if (!typePeriods.length) {
      setFromId('')
      setToId('')
      return
    }
    const latest = typePeriods[typePeriods.length - 1]
    let prev = typePeriods[typePeriods.length - 2] || latest
    if (type === 'year' && prev) {
      const y = latest.period_start.slice(0, 4)
      const mmdd = latest.period_start.slice(5)
      const diffYear = typePeriods.filter(
        (p) => p.id !== latest.id && p.period_start.slice(0, 4) !== y,
      )
      const sameMonth = diffYear.filter((p) => p.period_start.slice(5) === mmdd)
      prev = sameMonth.length
        ? sameMonth[sameMonth.length - 1]
        : diffYear.length
          ? diffYear[diffYear.length - 1]
          : latest
    }
    setFromId(prev ? String(prev.id) : String(latest.id))
    setToId(String(latest.id))
    setResult(null)
  }, [type, typePeriods])

  const toPeriod = typePeriods.find((p) => String(p.id) === toId)
  // For YoY only periods from a different calendar year than the current one are valid baselines.
  const baselineOptions =
    type === 'year' && toPeriod
      ? typePeriods.filter(
          (p) => String(p.id) !== toId && p.period_start.slice(0, 4) !== toPeriod.period_start.slice(0, 4),
        )
      : typePeriods
  const noYoYBaseline = type === 'year' && toPeriod && baselineOptions.length === 0

  const handleCompare = async () => {
    if (!fromId || !toId) {
      setError('Select two periods to compare.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const { data } = await client.get('/insights/compare', {
        params: { type, from_id: fromId, to_id: toId },
      })
      setResult(data)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setLoading(false)
    }
  }

  const errMsg = async (e) => {
    if (e?.response?.data instanceof Blob) {
      try {
        const t = JSON.parse(await e.response.data.text())
        return t.message || t.detail || 'Export failed.'
      } catch {
        return 'Export failed.'
      }
    }
    return apiError(e)
  }

  const download = async (format) => {
    if (!fromId || !toId) return
    setDownloading(format)
    setError('')
    try {
      const response = await client.post(
        '/reports/generate',
        { format, compare_type: type, from_id: Number(fromId), to_id: Number(toId) },
        { responseType: 'blob' },
      )
      const arrayBuf = response.data instanceof Blob
        ? await response.data.arrayBuffer()
        : response.data instanceof ArrayBuffer
          ? response.data
          : await new Blob([response.data]).arrayBuffer()
      const header = new Uint8Array(arrayBuf, 0, 2)
      const isPK = header[0] === 0x50 && header[1] === 0x4B

      if (!isPK) {
        try {
          const text = new TextDecoder().decode(arrayBuf)
          const err = JSON.parse(text)
          setError(err.message || err.detail || 'Export failed.')
        } catch {
          setError('Export failed.')
        }
        return
      }

      const isExcel = format === 'comparison_xlsx'
      const PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
      const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      const mimeType = isExcel ? XLSX_MIME : PPTX_MIME
      const ext = isExcel ? '.xlsx' : '.pptx'

      let filename = `ai_analysis_${type}_${fromId}_${toId}${ext}`
      try {
        const cd = response.headers['content-disposition'] || ''
        const match = cd.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
        if (match && match[1]) filename = match[1].replace(/["']/g, '').trim()
      } catch { /* ignored */ }

      const blob = new Blob([arrayBuf], { type: mimeType })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (e) {
      setError(await errMsg(e))
    } finally {
      setDownloading('')
    }
  }

  const fromPeriod = typePeriods.find((p) => String(p.id) === fromId)

  return (
    <div className="space-y-4">
      <Card
        title="🤖 Data Analysis AI — Period-over-Period"
        subtitle="Compare two fixed reporting windows week-over-week, month-over-month or year-over-year with AI-driven insights."
      >
        <div className="flex flex-wrap items-center gap-2">
          {COMPARE_TYPES.map((t) => (
            <button
              key={t.key}
              onClick={() => setType(t.key)}
              className={`rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                type === t.key
                  ? 'bg-indigo-600 text-white shadow-md'
                  : 'border border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="block">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Baseline period (earlier)
            </span>
            <select
              value={fromId}
              onChange={(e) => {
                setFromId(e.target.value)
                setResult(null)
              }}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-indigo-400 focus:outline-none"
            >
              {baselineOptions.length === 0 && (
                <option value="">
                  {type === 'year' ? 'No prior-year baseline available' : 'No periods available'}
                </option>
              )}
              {baselineOptions.map((p) => (
                <option key={p.id} value={p.id}>
                  {periodLabel(p)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Current period (later)
            </span>
            <select
              value={toId}
              onChange={(e) => {
                setToId(e.target.value)
                setResult(null)
              }}
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:border-indigo-400 focus:outline-none"
            >
              {typePeriods.length === 0 && <option value="">No periods available</option>}
              {typePeriods.map((p) => (
                <option key={p.id} value={p.id}>
                  {periodLabel(p)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {type === 'year' && (
          <p className="mt-2 text-[11px] text-slate-500">
            Year-over-year uses monthly periods — the baseline is auto-picked as the same calendar month one year earlier.
          </p>
        )}
        {noYoYBaseline && (
          <p className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-800">
            ⚠ No monthly periods from a previous year exist for the selected current period — pick a different current period to enable a year-over-year comparison.
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            onClick={handleCompare}
            disabled={loading || !fromId || !toId}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-2"
          >
            {loading ? <Spinner label="" /> : '⚡'} Compare Periods
          </button>

          <button
            onClick={() => download('comparison_ppt')}
            disabled={Boolean(downloading) || !fromId || !toId}
            className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-2"
          >
            {downloading === 'comparison_ppt' ? 'Generating…' : '📊 Export Comparison PPT'}
          </button>

          <button
            onClick={() => download('comparison_xlsx')}
            disabled={Boolean(downloading) || !fromId || !toId}
            className="rounded-xl border border-slate-600 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-40 transition-all flex items-center gap-2"
          >
            {downloading === 'comparison_xlsx' ? 'Generating…' : '📥 Export Comparison Excel'}
          </button>
        </div>
      </Card>

      {error && <ErrorBox message={error} />}

      {result && (
        <>
          {/* KPI cards */}
          <Card
            title={`${result.comparison_label} — ${toPeriod ? toPeriod.period_start : ''} vs ${fromPeriod ? fromPeriod.period_start : ''}`}
            subtitle="AI DATA ANALYSIS · deltas shown vs baseline"
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
              <DeltaKpi label="Total cases" a={result.period_a.total} b={result.period_b.total} delta={result.totals.delta_total} pct={result.totals.pct_total} />
              <DeltaKpi label="New" a={result.period_a.new} b={result.period_b.new} delta={result.totals.delta_new} pct={result.totals.pct_new} />
              <DeltaKpi label="Follow-up" a={result.period_a.followup} b={result.period_b.followup} delta={result.totals.delta_followup} pct={result.totals.pct_followup} />
              <DeltaKpi label="Sessions" a={result.period_a.total_sessions} b={result.period_b.total_sessions} delta={result.totals.delta_sessions} pct={result.totals.pct_sessions} />
              <DeltaKpi label="Active cases" a={result.totals.active_a || 0} b={result.totals.active_b || 0} delta={result.totals.delta_active} pct={result.totals.pct_active} />
            </div>
          </Card>

          {/* AI insights */}
          <Card title="🧠 AI Insights" subtitle="Generated narrative for this comparison">
            <InsightBullets insights={result.insights} limit={8} />
          </Card>

          {/* Top movers */}
          {result.movers?.length > 0 && (
            <Card title="📈 Top Category Changes" subtitle="Largest absolute shifts between the two periods">
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-900 text-white font-bold">
                    <tr>
                      <th className="px-3 py-2 text-left">Category</th>
                      <th className="px-3 py-2 text-left">Label</th>
                      <th className="px-3 py-2 text-center">Baseline</th>
                      <th className="px-3 py-2 text-center">Current</th>
                      <th className="px-3 py-2 text-center">Δ</th>
                      <th className="px-3 py-2 text-center">Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.movers.map((m, i) => (
                      <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2 text-slate-500">{GROUP_TITLES[m.category] || m.category}</td>
                        <td className="px-3 py-2 font-semibold text-slate-800">{m.label}</td>
                        <td className="px-3 py-2 text-center text-slate-600">{number.format(m.a)}</td>
                        <td className="px-3 py-2 text-center text-slate-600">{number.format(m.b)}</td>
                        <td className={`px-3 py-2 text-center font-bold ${deltaColor(m.delta)}`}>
                          {m.delta > 0 ? '+' : ''}
                          {number.format(m.delta)}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${m.delta > 0 ? 'bg-emerald-100 text-emerald-700' : m.delta < 0 ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-500'}`}>
                            {m.delta > 0 ? '▲ UP' : m.delta < 0 ? '▼ DOWN' : '—'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Category deltas */}
          <Card title="🧩 Category Breakdown — period-over-period" subtitle="Full category-wise deltas">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Object.entries(result.category_deltas || {}).map(([groupKey, entries]) => {
                const withChanges = entries.filter((e) => e.delta || e.a || e.b)
                return (
                  <div key={groupKey} className="overflow-hidden rounded-xl border border-slate-200">
                    <div className="bg-slate-800 px-3 py-2 text-xs font-bold text-white uppercase tracking-wide">
                      {GROUP_TITLES[groupKey] || groupKey}
                    </div>
                    <table className="min-w-full text-[11px]">
                      <tbody>
                        {withChanges.map((e, i) => (
                          <tr key={e.key || i} className="border-b border-slate-100">
                            <td className="px-3 py-1.5 text-slate-700">{e.label}</td>
                            <td className="px-2 py-1.5 text-center text-slate-500">{number.format(e.a)}</td>
                            <td className="px-2 py-1.5 text-center text-slate-500">{number.format(e.b)}</td>
                            <td className={`px-2 py-1.5 text-center font-bold ${deltaColor(e.delta)}`}>
                              {e.delta > 0 ? '+' : ''}
                              {number.format(e.delta)}
                            </td>
                            <td className={`px-2 py-1.5 text-right font-semibold ${deltaColor(e.delta)}`}>
                              {fmtPct(e.pct)}
                            </td>
                          </tr>
                        ))}
                        {withChanges.length === 0 && (
                          <tr>
                            <td className="px-3 py-2 text-slate-400">No changes</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

// Latest matching periods in a memoised, sorted array.
function usePeriodsOf(periods, reportType) {
  return useMemo(
    () =>
      periods
        .filter((p) => p.report_type === reportType)
        .sort((a, b) => a.period_start.localeCompare(b.period_start)),
    [periods, reportType],
  )
}
