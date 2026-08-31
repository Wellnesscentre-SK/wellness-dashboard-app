import { useEffect, useMemo, useState } from 'react'
import client, { apiError } from '../api/client'
import { Card, ErrorBox, Spinner } from '../components/ui'

const TABS = [
  { key: 'weekly', label: '📅 Weekly Reports' },
  { key: 'monthly', label: '🗓️ Monthly Reports' },
  { key: 'yearly', label: '📊 Yearly Reports' },
]

const btnPrimary = 'rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-40 transition-all shadow-md'
const btnDark = 'rounded-xl border border-slate-600 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 disabled:opacity-40 transition-all'
const btnCompare = 'rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-40 transition-all shadow-md'
const selectCls = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:border-indigo-500 focus:outline-none'

export default function ReportsCenter() {
  const [options, setOptions] = useState(null)
  const [tab, setTab] = useState('weekly')
  const [year, setYear] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  // selections
  const [weekId, setWeekId] = useState('')
  const [monthKey, setMonthKey] = useState('')
  const [yearSel, setYearSel] = useState('')
  // compare selections
  const [cmpWeekA, setCmpWeekA] = useState('')
  const [cmpWeekB, setCmpWeekB] = useState('')
  const [cmpMonthA, setCmpMonthA] = useState('')
  const [cmpMonthB, setCmpMonthB] = useState('')
  const [cmpYearA, setCmpYearA] = useState('')
  const [cmpYearB, setCmpYearB] = useState('')

  useEffect(() => {
    ;(async () => {
      try {
        const { data } = await client.get('/reports/build')
        setOptions(data)
        if (data.years?.length) setYear(String(data.years[0]))
      } catch (e) {
        setError(apiError(e))
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const years = options?.years || []

  const weeksForYear = useMemo(
    () => (options?.weekly || []).filter((w) => w.start.slice(0, 4) === String(year)),
    [options, year],
  )

  const monthsForYear = useMemo(
    () => options?.months?.[String(year)] || [],
    [options, year],
  )

  const allMonthKeys = useMemo(() => {
    const keys = []
    const sortedYears = [...(options?.years || [])].sort()
    for (const y of sortedYears) {
      for (const m of options?.months?.[String(y)] || []) {
        keys.push({ value: `${y}-${String(m.month).padStart(2, '0')}`, label: `${m.label} ${y}` })
      }
    }
    return keys
  }, [options])

  const selectedMonth = monthsForYear.find(
    (m) => `${year}-${String(m.month).padStart(2, '0')}` === monthKey,
  )

  const download = async (payload, busyKey) => {
    setBusy(busyKey)
    setError('')
    try {
      const response = await client.post('/reports/build', payload, { responseType: 'blob' })
      const ct = (response.headers['content-type'] || '').toLowerCase().split(';')[0].trim()

      // If the server returned a JSON/text error, parse and show it
      if (ct.includes('application/json') || ct.includes('text/')) {
        try {
          const text = await response.data.text()
          const err = JSON.parse(text)
          setError(err.message || err.detail || 'Generation failed.')
        } catch {
          setError('Generation failed.')
        }
        return
      }

      // --- Determine correct file extension ---
      let filename = 'report'
      const disposition = response.headers['content-disposition'] || ''
      const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (match && match[1]) filename = match[1].replace(/['"]/g, '').trim()

      // Determine MIME type for the Blob and correct extension
      let mimeType = ct || 'application/octet-stream'
      const ext = (filename.split('.').pop() || '').toLowerCase()
      const knownExts = ['pptx', 'xlsx', 'ppt', 'xls']

      // Infer extension from content-type if missing or wrong
      if (!knownExts.includes(ext)) {
        if (ct.includes('presentationml') || ct.includes('powerpoint')) {
          filename = filename.replace(/\.[^.]*$/, '') + '.pptx'
          mimeType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        } else if (ct.includes('spreadsheetml') || ct.includes('excel')) {
          filename = filename.replace(/\.[^.]*$/, '') + '.xlsx'
          mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        } else {
          // Last-resort fallback: infer from the payload's format field
          const fmt = String(payload.format || 'ppt').toLowerCase()
          if (fmt === 'xlsx') {
            filename = (filename === 'report' ? 'report' : filename.replace(/\.[^.]*$/, '')) + '.xlsx'
            mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
          } else {
            filename = (filename === 'report' ? 'report' : filename.replace(/\.[^.]*$/, '')) + '.pptx'
            mimeType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
          }
        }
      } else {
        // Known extension – ensure mimeType matches
        if (ext === 'pptx') mimeType = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        else if (ext === 'xlsx') mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      }

      // Trigger download with proper MIME type so OS opens it correctly
      const blob = new Blob([response.data], { type: mimeType })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(await blobError(e))
    } finally {
      setBusy('')
    }
  }

  const blobError = async (e) => {
    if (e?.response?.data instanceof Blob) {
      try {
        const t = JSON.parse(await e.response.data.text())
        return t.message || t.detail || 'Generation failed.'
      } catch {
        return 'Generation failed.'
      }
    }
    return apiError(e)
  }

  if (loading) return <Spinner label="Loading report modules…" />

  return (
    <div className="space-y-5 max-w-6xl">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Report Center</h1>
        <p className="text-xs text-slate-500 mt-1">
          Separate Weekly, Monthly and Yearly modules. Monthly reports automatically combine every
          weekly entry of the month (1st–last day); yearly reports combine January–December monthly
          data. Everything is regenerated live, so new weekly data is always included and duplicates
          are impossible.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-xl px-4 py-2 text-xs font-bold transition-all ${
              tab === t.key
                ? 'bg-indigo-600 text-white shadow-md'
                : 'border border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold text-slate-500">Date Filter — Year:</span>
        <select className={selectCls} value={year} onChange={(e) => setYear(e.target.value)}>
          {years.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      <ErrorBox message={error} />

      {/* ── WEEKLY MODULE ─────────────────────────────────────────────── */}
      {tab === 'weekly' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Generate Weekly Report" subtitle="Every detected weekly entry, PPT or Excel.">
            {!weeksForYear.length && <p className="text-xs text-slate-500">No weekly entries for {year}.</p>}
            <div className="space-y-2 max-h-64 overflow-auto">
              {weeksForYear.map((w) => (
                <label key={w.id} className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-xs cursor-pointer ${
                  String(w.id) === weekId ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'}`}>
                  <input type="radio" name="week" checked={String(w.id) === weekId} onChange={() => setWeekId(String(w.id))} />
                  <span className="text-slate-700">{w.label}</span>
                  <span className="ml-auto text-slate-400">{w.start} → {w.end}</span>
                </label>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <button className={btnPrimary} disabled={!weekId || !!busy}
                onClick={() => download({ report_type: 'weekly', format: 'ppt', period_id: Number(weekId) }, 'wk-ppt')}>
                {busy === 'wk-ppt' ? 'Generating…' : '📊 Generate PPT'}
              </button>
              <button className={btnDark} disabled={!weekId || !!busy}
                onClick={() => download({ report_type: 'weekly', format: 'xlsx', period_id: Number(weekId) }, 'wk-xlsx')}>
                {busy === 'wk-xlsx' ? 'Generating…' : '📥 Generate Excel'}
              </button>
            </div>
          </Card>

          <Card title="Week-to-Week Comparison" subtitle="Pick any two weekly entries to compare.">
            <div className="grid grid-cols-2 gap-3">
              <select className={selectCls} value={cmpWeekA} onChange={(e) => setCmpWeekA(e.target.value)}>
                <option value="">From week…</option>
                {weeksForYear.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
              </select>
              <select className={selectCls} value={cmpWeekB} onChange={(e) => setCmpWeekB(e.target.value)}>
                <option value="">To week…</option>
                {weeksForYear.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
              </select>
            </div>
            <button className={`${btnCompare} mt-4`} disabled={!cmpWeekA || !cmpWeekB || cmpWeekA === cmpWeekB || !!busy}
              onClick={() => download({ compare: { type: 'week', from_id: Number(cmpWeekA), to_id: Number(cmpWeekB) } }, 'wk-cmp')}>
              {busy === 'wk-cmp' ? 'Comparing…' : '⚖️ Compare PPT'}
            </button>
          </Card>
        </div>
      )}

      {/* ── MONTHLY MODULE ────────────────────────────────────────────── */}
      {tab === 'monthly' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Generate Monthly Report" subtitle={`All weekly data of the month combined automatically (${year}).`}>
            {!monthsForYear.length && <p className="text-xs text-slate-500">No data for {year}.</p>}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {monthsForYear.map((m) => {
                const key = `${year}-${String(m.month).padStart(2, '0')}`
                return (
                  <button key={key} onClick={() => setMonthKey(key)}
                    className={`rounded-lg border px-3 py-2 text-left text-xs transition-all ${
                      monthKey === key ? 'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-300' : 'border-slate-200 hover:bg-slate-50'}`}>
                    <div className="font-bold text-slate-700">{m.label}</div>
                    <div className="text-[10px] text-slate-500">
                      {m.week_count > 0 ? `combines ${m.week_count} week${m.week_count > 1 ? 's' : ''}` : 'monthly entry'}
                    </div>
                  </button>
                )
              })}
            </div>
            {selectedMonth && (
              <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
                ✔ Will auto-combine <b>{selectedMonth.week_count || 0}</b> weekly entr{selectedMonth.week_count === 1 ? 'y' : 'ies'} for
                the full month (1st–last day).
              </p>
            )}
            <div className="mt-4 flex gap-2">
              <button className={btnPrimary} disabled={!monthKey || !!busy}
                onClick={() => download({ report_type: 'monthly', format: 'ppt', year: Number(year), month: selectedMonth?.month }, 'mo-ppt')}>
                {busy === 'mo-ppt' ? 'Generating…' : '📊 Generate PPT'}
              </button>
              <button className={btnDark} disabled={!monthKey || !!busy}
                onClick={() => download({ report_type: 'monthly', format: 'xlsx', year: Number(year), month: selectedMonth?.month }, 'mo-xlsx')}>
                {busy === 'mo-xlsx' ? 'Generating…' : '📥 Generate Excel'}
              </button>
            </div>
          </Card>

          <Card title="Month-to-Month Comparison" subtitle="Compares the combined totals of any two months.">
            <div className="grid grid-cols-2 gap-3">
              <select className={selectCls} value={cmpMonthA} onChange={(e) => setCmpMonthA(e.target.value)}>
                <option value="">From month…</option>
                {allMonthKeys.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
              <select className={selectCls} value={cmpMonthB} onChange={(e) => setCmpMonthB(e.target.value)}>
                <option value="">To month…</option>
                {allMonthKeys.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
            </div>
            <button className={`${btnCompare} mt-4`} disabled={!cmpMonthA || !cmpMonthB || cmpMonthA === cmpMonthB || !!busy}
              onClick={() => download({ compare: { type: 'month', from_month: cmpMonthA, to_month: cmpMonthB } }, 'mo-cmp')}>
              {busy === 'mo-cmp' ? 'Comparing…' : '⚖️ Compare PPT'}
            </button>
          </Card>
        </div>
      )}

      {/* ── YEARLY MODULE ─────────────────────────────────────────────── */}
      {tab === 'yearly' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Generate Yearly Report" subtitle="January 1 – December 31 combined into one annual analysis.">
            <div className="flex flex-wrap gap-2">
              {years.map((y) => {
                const months = options?.months?.[String(y)] || []
                return (
                  <button key={y} onClick={() => setYearSel(String(y))}
                    className={`rounded-lg border px-4 py-2 text-xs transition-all ${
                      yearSel === String(y) ? 'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-300' : 'border-slate-200 hover:bg-slate-50'}`}>
                    <div className="font-bold text-slate-700">{y} Data Analysis</div>
                    <div className="text-[10px] text-slate-500">{months.length} months available</div>
                  </button>
                )
              })}
            </div>
            <div className="mt-4 flex gap-2">
              <button className={btnPrimary} disabled={!yearSel || !!busy}
                onClick={() => download({ report_type: 'yearly', format: 'ppt', year: Number(yearSel) }, 'yr-ppt')}>
                {busy === 'yr-ppt' ? 'Generating…' : '📊 Generate PPT'}
              </button>
              <button className={btnDark} disabled={!yearSel || !!busy}
                onClick={() => download({ report_type: 'yearly', format: 'xlsx', year: Number(yearSel) }, 'yr-xlsx')}>
                {busy === 'yr-xlsx' ? 'Generating…' : '📥 Generate Excel'}
              </button>
            </div>
          </Card>

          <Card title="Year-to-Year Comparison" subtitle="Full-year vs full-year combined analysis.">
            <div className="grid grid-cols-2 gap-3">
              <select className={selectCls} value={cmpYearA} onChange={(e) => setCmpYearA(e.target.value)}>
                <option value="">From year…</option>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
              <select className={selectCls} value={cmpYearB} onChange={(e) => setCmpYearB(e.target.value)}>
                <option value="">To year…</option>
                {years.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <button className={`${btnCompare} mt-4`} disabled={!cmpYearA || !cmpYearB || cmpYearA === cmpYearB || !!busy}
              onClick={() => download({ compare: { type: 'year', from_year: Number(cmpYearA), to_year: Number(cmpYearB) } }, 'yr-cmp')}>
              {busy === 'yr-cmp' ? 'Comparing…' : '⚖️ Compare PPT'}
            </button>
          </Card>
        </div>
      )}
    </div>
  )
}
