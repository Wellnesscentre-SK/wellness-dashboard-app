import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../auth/useAuth'
import client, { apiError } from '../api/client'

const MODES = [
  { key: 'weekly', label: 'Weekly' },
  { key: 'monthly', label: 'Monthly' },
  { key: 'yearly', label: 'Yearly' },
  { key: 'comparison', label: 'Comparison' },
]

const PRIORITY_COLORS = {
  HIGH: 'bg-red-100 text-red-700 border-red-200',
  MEDIUM: 'bg-amber-100 text-amber-700 border-amber-200',
  LOW: 'bg-green-100 text-green-700 border-green-200',
}

const CATEGORY_COLORS = {
  'Performance Improvement': 'bg-blue-50 text-blue-700',
  'Client Engagement': 'bg-purple-50 text-purple-700',
  'Operational Improvement': 'bg-orange-50 text-orange-700',
  'Team Development': 'bg-teal-50 text-teal-700',
  'Wellness Centre Development': 'bg-indigo-50 text-indigo-700',
  'Reporting & Data Quality': 'bg-slate-100 text-slate-700',
  'Future Opportunities': 'bg-emerald-50 text-emerald-700',
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      <span className="ml-3 text-sm text-slate-500">AI is analyzing the report...</span>
    </div>
  )
}

function KpiCard({ label, value, color }) {
  return (
    <div className={`rounded-xl border px-4 py-3 text-center ${color}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs mt-1 opacity-75">{label}</div>
    </div>
  )
}

function SuggestionCard({ rec, index, onAddToPlan }) {
  const [expanded, setExpanded] = useState(false)
  const pColor = PRIORITY_COLORS[rec.priority] || PRIORITY_COLORS.MEDIUM
  const cColor = CATEGORY_COLORS[rec.category_label] || 'bg-slate-50 text-slate-700'

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-sm transition-shadow">
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-mono text-slate-400">#{index + 1}</span>
              <h3 className="text-sm font-semibold text-slate-900 truncate">{rec.title}</h3>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${pColor}`}>
                {rec.priority}
              </span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${cColor}`}>
                {rec.category_label}
              </span>
              {rec.confidence && (
                <span className="text-[10px] text-slate-400">
                  Evidence: {rec.confidence}
                </span>
              )}
            </div>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-slate-400 hover:text-slate-600 text-xs shrink-0"
          >
            {expanded ? 'Less' : 'Details'}
          </button>
        </div>

        {rec.why && (
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">{rec.why}</p>
        )}

        {expanded && (
          <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
            {rec.evidence && (
              <div>
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Evidence</span>
                <p className="text-xs text-slate-700 mt-0.5">{rec.evidence}</p>
              </div>
            )}
            {rec.action && (
              <div>
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Recommended Action</span>
                <p className="text-xs text-slate-700 mt-0.5">{rec.action}</p>
              </div>
            )}
            {rec.benefit && (
              <div>
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Expected Benefit</span>
                <p className="text-xs text-green-700 mt-0.5">{rec.benefit}</p>
              </div>
            )}
            <div className="flex gap-4">
              {rec.timeline && (
                <div>
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Timeline</span>
                  <p className="text-xs text-slate-700 mt-0.5">{rec.timeline}</p>
                </div>
              )}
              {rec.success_metric && (
                <div>
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Success Metric</span>
                  <p className="text-xs text-slate-700 mt-0.5">{rec.success_metric}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="px-4 py-2 bg-slate-50 border-t border-slate-100 flex justify-end">
        <button
          onClick={() => onAddToPlan(rec)}
          className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
        >
          + Add to Action Plan
        </button>
      </div>
    </div>
  )
}

function RoadmapSection({ roadmap }) {
  const phases = [
    { key: 'immediate', color: 'border-red-400 bg-red-50', label: 'IMMEDIATE (0-7 Days)' },
    { key: 'short_term', color: 'border-amber-400 bg-amber-50', label: 'SHORT TERM (1-4 Weeks)' },
    { key: 'medium_term', color: 'border-blue-400 bg-blue-50', label: 'MEDIUM TERM (1-3 Months)' },
    { key: 'long_term', color: 'border-green-400 bg-green-50', label: 'LONG TERM (3-12 Months)' },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {phases.map(({ key, color, label }) => {
        const items = roadmap[key]?.items || []
        return (
          <div key={key} className={`rounded-xl border-l-4 ${color} p-4`}>
            <h4 className="text-xs font-bold text-slate-700 mb-3 uppercase tracking-wide">{label}</h4>
            {items.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No items</p>
            ) : (
              <ul className="space-y-2">
                {items.map((item, i) => (
                  <li key={i} className="text-xs text-slate-700">
                    <span className="font-medium">{item.title}</span>
                    {item.priority && (
                      <span className={`ml-1.5 inline-block px-1.5 py-0 rounded text-[9px] font-semibold ${
                        item.priority === 'HIGH' ? 'bg-red-200 text-red-700' :
                        item.priority === 'MEDIUM' ? 'bg-amber-200 text-amber-700' :
                        'bg-green-200 text-green-700'
                      }`}>{item.priority}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ActionPlanList({ plans, onRefresh }) {
  const [editing, setEditing] = useState(null)
  const [statusVal, setStatusVal] = useState('')

  const updateStatus = async (id, status) => {
    try {
      await client.patch(`/ai/action-plan/${id}`, { status })
      onRefresh()
    } catch (err) {
      console.error(err)
    }
  }

  const deletePlan = async (id) => {
    if (!confirm('Delete this action plan item?')) return
    try {
      await client.delete(`/ai/action-plan/${id}`)
      onRefresh()
    } catch (err) {
      console.error(err)
    }
  }

  const statusOptions = ['not_started', 'in_progress', 'completed', 'deferred']
  const statusLabels = { not_started: 'Not Started', in_progress: 'In Progress', completed: 'Completed', deferred: 'Deferred' }

  if (plans.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400 text-sm">
        No action plan items yet. Add recommendations from the AI Suggestions above.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-slate-200">
            <th className="text-left py-2 px-3 font-semibold text-slate-600">Recommendation</th>
            <th className="text-left py-2 px-3 font-semibold text-slate-600">Priority</th>
            <th className="text-left py-2 px-3 font-semibold text-slate-600">Category</th>
            <th className="text-left py-2 px-3 font-semibold text-slate-600">Owner</th>
            <th className="text-left py-2 px-3 font-semibold text-slate-600">Status</th>
            <th className="text-left py-2 px-3 font-semibold text-slate-600">Actions</th>
          </tr>
        </thead>
        <tbody>
          {plans.map((plan) => (
            <tr key={plan.id} className="border-b border-slate-100 hover:bg-slate-50">
              <td className="py-2 px-3 max-w-xs truncate">{plan.title}</td>
              <td className="py-2 px-3">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  plan.priority === 'HIGH' ? 'bg-red-100 text-red-700' :
                  plan.priority === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                  'bg-green-100 text-green-700'
                }`}>{plan.priority}</span>
              </td>
              <td className="py-2 px-3 text-slate-600">{plan.category}</td>
              <td className="py-2 px-3 text-slate-600">{plan.responsible_person || '—'}</td>
              <td className="py-2 px-3">
                <select
                  value={plan.status}
                  onChange={(e) => updateStatus(plan.id, e.target.value)}
                  className="rounded border border-slate-200 px-1.5 py-0.5 text-[10px] bg-white"
                >
                  {statusOptions.map(s => (
                    <option key={s} value={s}>{statusLabels[s]}</option>
                  ))}
                </select>
              </td>
              <td className="py-2 px-3">
                <button onClick={() => deletePlan(plan.id)} className="text-red-400 hover:text-red-600 text-[10px]">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function AISuggestions() {
  const { user } = useAuth()
  const [mode, setMode] = useState('weekly')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [periods, setPeriods] = useState([])
  const [selectedPeriod, setSelectedPeriod] = useState('')
  const [prevPeriod, setPrevPeriod] = useState('')
  const [monthYear, setMonthYear] = useState('')
  const [yearVal, setYearVal] = useState(new Date().getFullYear())
  const [compareType, setCompareType] = useState('week')
  const [compareFrom, setCompareFrom] = useState('')
  const [compareTo, setCompareTo] = useState('')
  const [actionPlans, setActionPlans] = useState([])
  const [activeTab, setActiveTab] = useState('suggestions')
  const [exportingPpt, setExportingPpt] = useState(false)

  useEffect(() => {
    client.get('/periods').then(({ data }) => setPeriods(data)).catch(() => {})
  }, [])

  useEffect(() => {
    client.get('/ai/action-plan').then(({ data }) => setActionPlans(data)).catch(() => {})
  }, [])

  const weeklyPeriods = periods.filter(p => p.report_type === 'weekly')
  const monthlyPeriods = periods.filter(p => p.report_type === 'monthly')

  const generate = useCallback(async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const payload = { mode }
      if (mode === 'weekly') {
        payload.period_id = selectedPeriod
      } else if (mode === 'monthly') {
        const [y, m] = (monthYear || '').split('-')
        payload.year = parseInt(y) || yearVal
        payload.month = parseInt(m) || new Date().getMonth() + 1
      } else if (mode === 'yearly') {
        payload.year = yearVal
      } else if (mode === 'comparison') {
        payload.compare_type = compareType
        payload.from_id = parseInt(compareFrom)
        payload.to_id = parseInt(compareTo)
      }
      const { data } = await client.post('/ai/suggestions', payload)
      setResult(data)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setLoading(false)
    }
  }, [mode, selectedPeriod, monthYear, yearVal, compareType, compareFrom, compareTo])

  const addToPlan = async (rec) => {
    try {
      await client.post('/ai/action-plan', {
        title: rec.title,
        category: rec.category_label || rec.category,
        priority: rec.priority,
        recommendation: rec.why || '',
        evidence: rec.evidence || '',
        action: rec.action || '',
        expected_result: rec.benefit || '',
        source_type: result?.mode || mode,
        source_mode: mode,
      })
      const { data } = await client.get('/ai/action-plan')
      setActionPlans(data)
    } catch (err) {
      alert(apiError(err))
    }
  }

  const refreshPlans = async () => {
    try {
      const { data } = await client.get('/ai/action-plan')
      setActionPlans(data)
    } catch {}
  }

  const exportPpt = async () => {
    if (!result) return
    setExportingPpt(true)
    try {
      const { data: summary } = await client.post('/ai/export', { result })
      const blob = new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ai_insights_${mode}_${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      alert(apiError(err))
    } finally {
      setExportingPpt(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">AI Insights & Improvement Suggestions</h1>
            <p className="text-sm text-slate-500">AI-powered analysis of Wellness Centre performance with actionable improvement recommendations.</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5">
        <div className="flex items-center gap-2 mb-4">
          {MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => { setMode(m.key); setResult(null); setError('') }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                mode === m.key
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {mode === 'weekly' && (
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Select Week</label>
              <select
                value={selectedPeriod}
                onChange={(e) => setSelectedPeriod(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Choose a period...</option>
                {weeklyPeriods.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.period_start} to {p.period_end}
                  </option>
                ))}
              </select>
            </div>
          )}
          {mode === 'monthly' && (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Year</label>
                <input
                  type="number"
                  value={yearVal}
                  onChange={(e) => setYearVal(parseInt(e.target.value))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Month</label>
                <select
                  value={monthYear}
                  onChange={(e) => setMonthYear(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Choose month...</option>
                  {['01','02','03','04','05','06','07','08','09','10','11','12'].map(m => (
                    <option key={m} value={`${yearVal}-${m}`}>
                      {new Date(2024, parseInt(m) - 1).toLocaleString('default', { month: 'long' })}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
          {mode === 'yearly' && (
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Year</label>
              <input
                type="number"
                value={yearVal}
                onChange={(e) => setYearVal(parseInt(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}
          {mode === 'comparison' && (
            <>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Comparison Type</label>
                <select
                  value={compareType}
                  onChange={(e) => setCompareType(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="week">Week vs Week</option>
                  <option value="month">Month vs Month</option>
                  <option value="year">Year vs Year</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">From Period</label>
                <select
                  value={compareFrom}
                  onChange={(e) => setCompareFrom(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select...</option>
                  {periods.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.report_type} {p.period_start}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">To Period</label>
                <select
                  value={compareTo}
                  onChange={(e) => setCompareTo(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select...</option>
                  {periods.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.report_type} {p.period_start}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={generate}
            disabled={loading}
            className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Analyzing...' : 'Generate AI Suggestions'}
          </button>
          {result && (
            <button
              onClick={exportPpt}
              disabled={exportingPpt}
              className="px-4 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              {exportingPpt ? 'Exporting...' : 'Export JSON'}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading && <Spinner />}

      {result && !loading && (
        <>
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
              <KpiCard label="AI Insights" value={result.kpi?.total_suggestions || 0} color="bg-indigo-50 text-indigo-700 border border-indigo-200" />
              <KpiCard label="High Priority" value={result.kpi?.high || 0} color="bg-red-50 text-red-700 border border-red-200" />
              <KpiCard label="Medium Priority" value={result.kpi?.medium || 0} color="bg-amber-50 text-amber-700 border border-amber-200" />
              <KpiCard label="Low Priority" value={result.kpi?.low || 0} color="bg-green-50 text-green-700 border border-green-200" />
              <KpiCard label="Opportunities" value={result.kpi?.opportunities || 0} color="bg-blue-50 text-blue-700 border border-blue-200" />
            </div>
            {result.summary && (
              <div className="bg-slate-50 rounded-lg p-4">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">AI Summary</h3>
                <p className="text-sm text-slate-700">{result.summary}</p>
              </div>
            )}
          </div>

          <div className="flex gap-1 bg-slate-100 rounded-lg p-1 w-fit">
            {[
              { key: 'suggestions', label: 'Recommendations' },
              { key: 'roadmap', label: 'Roadmap' },
              { key: 'action_plan', label: 'Action Plan' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.key
                    ? 'bg-white text-indigo-600 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'suggestions' && result.suggestions && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {result.suggestions.map((rec, i) => (
                <SuggestionCard key={i} rec={rec} index={i} onAddToPlan={addToPlan} />
              ))}
            </div>
          )}

          {activeTab === 'roadmap' && result.roadmap && (
            <RoadmapSection roadmap={result.roadmap} />
          )}

          {activeTab === 'action_plan' && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">AI Improvement Action Plan</h3>
              <ActionPlanList plans={actionPlans} onRefresh={refreshPlans} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
