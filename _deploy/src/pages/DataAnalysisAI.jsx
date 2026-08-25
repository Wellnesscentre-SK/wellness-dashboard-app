import { useState, useRef, useEffect, useCallback } from 'react'
import client, { apiError } from '../api/client'

const number = new Intl.NumberFormat('en-IN')

/* ─── Quick action chips ──────────────────────────────────────────────── */
const QUICK_ACTIONS = [
  { label: 'List all periods', msg: 'Show me all available reporting periods' },
  { label: 'Monthly trend', msg: 'What is the monthly case trend for the last 6 months?' },
  { label: 'Top concerns', msg: 'What are the top concerns students are facing?' },
  { label: 'Gender breakdown', msg: 'Show me the gender breakdown of cases' },
  { label: 'Compare teams', msg: 'Compare WC, Team A, YourDost, and Myndwell performance' },
  { label: 'Find anomalies', msg: 'Are there any anomalies or unusual patterns in the data?' },
  { label: 'Session modes', msg: 'How are sessions distributed across online, in-person, and phone?' },
  { label: 'Generate PPT report', msg: 'Generate a PPTX report for the latest period' },
]

/* ─── Markdown-ish renderer (bold, bullet, code) ────────────────────── */
function renderText(text) {
  if (!text) return null
  const lines = text.split('\n')
  return lines.map((line, i) => {
    if (line.startsWith('- ') || line.startsWith('* ')) {
      return (
        <li key={i} className="ml-4 list-disc text-sm leading-relaxed">
          {renderInline(line.slice(2))}
        </li>
      )
    }
    if (/^\d+\.\s/.test(line)) {
      return (
        <li key={i} className="ml-4 list-decimal text-sm leading-relaxed">
          {renderInline(line.replace(/^\d+\.\s/, ''))}
        </li>
      )
    }
    return (
      <p key={i} className="text-sm leading-relaxed">
        {renderInline(line) || '\u00A0'}
      </p>
    )
  })
}

function renderInline(text) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-indigo-700">{part.slice(1, -1)}</code>
    }
    return part
  })
}

/* ─── Data table renderer (from tool results) ────────────────────────── */
function DataTable({ data, title }) {
  if (!data || typeof data !== 'object') return null

  if (Array.isArray(data)) {
    if (data.length === 0) return <p className="text-xs text-slate-400 italic">No data</p>
    const keys = Object.keys(data[0])
    return (
      <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
        {title && <div className="bg-slate-800 px-3 py-1.5 text-[11px] font-bold text-white uppercase">{title}</div>}
        <table className="min-w-full text-[11px]">
          <thead className="bg-slate-100">
            <tr>{keys.map(k => <th key={k} className="px-3 py-1.5 text-left font-semibold text-slate-600">{k}</th>)}</tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} className="border-t border-slate-100 hover:bg-slate-50">
                {keys.map(k => <td key={k} className="px-3 py-1.5 text-slate-700">{typeof row[k] === 'number' ? number.format(row[k]) : String(row[k] ?? '')}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  // Object → key-value table
  const entries = Object.entries(data).filter(([k]) => !k.startsWith('_'))
  if (entries.length === 0) return null
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
      {title && <div className="bg-slate-800 px-3 py-1.5 text-[11px] font-bold text-white uppercase">{title}</div>}
      <table className="min-w-full text-[11px]">
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k} className="border-t border-slate-100">
              <td className="px-3 py-1.5 font-medium text-slate-600 whitespace-nowrap">{k.replace(/_/g, ' ')}</td>
              <td className="px-3 py-1.5 text-slate-800 font-semibold">
                {typeof v === 'number' ? number.format(v) : typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ─── Inline chart (simple horizontal bar) ───────────────────────────── */
function MiniBar({ items, maxVal }) {
  if (!items?.length) return null
  const mx = maxVal || Math.max(...items.map(i => i.value), 1)
  return (
    <div className="mt-2 space-y-1">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2 text-[11px]">
          <span className="w-28 truncate text-slate-600 font-medium">{item.label}</span>
          <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${(item.value / mx) * 100}%` }} />
          </div>
          <span className="w-12 text-right font-bold text-slate-800">{number.format(item.value)}</span>
        </div>
      ))}
    </div>
  )
}

/* ─── Tool result card ───────────────────────────────────────────────── */
function ToolResultCard({ tr }) {
  const [expanded, setExpanded] = useState(false)
  const result = tr.result
  if (!result) return null

  const title = tr.name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  // Generate chart data for specific tools
  let chartItems = null
  if (tr.name === 'get_top_concerns' && result.concerns) {
    chartItems = result.concerns.map(c => ({ label: c.label, value: c.count }))
  } else if (tr.name === 'get_gender_breakdown') {
    chartItems = [
      { label: 'Male', value: result.male },
      { label: 'Female', value: result.female },
      { label: 'Other', value: result.other },
    ]
  } else if (tr.name === 'get_session_mode_breakdown') {
    chartItems = [
      { label: 'Online', value: result.online },
      { label: 'In-Person', value: result.in_person },
      { label: 'Phone', value: result.phone },
    ]
  } else if (tr.name === 'compare_teams' && result.verticals) {
    chartItems = Object.entries(result.verticals).map(([k, v]) => ({ label: k, value: v.total }))
  } else if (tr.name === 'get_monthly_trend' && result.trend) {
    chartItems = result.trend.map(t => ({ label: t.label.slice(0, 7), value: t.total }))
  } else if (tr.name === 'find_anomalies' && result.anomalies?.length) {
    chartItems = result.anomalies.map(a => ({
      label: `${a.label} (${a.type})`,
      value: a.total,
    }))
  }

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-indigo-100 text-indigo-600 text-[10px] font-bold">
            {tr.name === 'generate_report' ? '📄' : '🔧'}
          </span>
          <span className="text-[11px] font-semibold text-slate-700">{title}</span>
        </div>
        <span className="text-[10px] text-slate-400">{expanded ? '▲ collapse' : '▼ expand'}</span>
      </button>
      {expanded && (
        <div className="border-t border-slate-200 px-3 py-2">
          {result.error ? (
            <p className="text-xs text-red-600">{result.error}</p>
          ) : result.periods ? (
            <DataTable data={result.periods} title="Periods" />
          ) : result.period ? (
            <DataTable data={result} title="KPI Summary" />
          ) : result.trend ? (
            <>
              <DataTable data={result.trend} title="Monthly Trend" />
              <MiniBar items={chartItems} />
            </>
          ) : result.anomalies ? (
            <>
              {result.stats && (
                <div className="mb-2 flex gap-3 text-[11px]">
                  <span>Mean: <strong>{number.format(result.stats.mean)}</strong></span>
                  <span>Std Dev: <strong>{result.stats.std}</strong></span>
                  <span>Periods: <strong>{result.stats.periods_analyzed}</strong></span>
                </div>
              )}
              {result.anomalies.length === 0 ? (
                <p className="text-xs text-emerald-600 font-medium">No anomalies detected.</p>
              ) : (
                <DataTable data={result.anomalies} title="Anomalies" />
              )}
            </>
          ) : result.action === 'generate_report' ? (
            <p className="text-xs text-amber-700 font-medium">{result.message}</p>
          ) : (
            <DataTable data={result} title={title} />
          )}
          {chartItems && chartItems.length > 0 && <MiniBar items={chartItems} />}
        </div>
      )}
    </div>
  )
}

/* ─── Approval button ────────────────────────────────────────────────── */
function ApprovalButton({ action, onApprove }) {
  if (!action || action.status !== 'pending_approval') return null
  return (
    <div className="mt-3 rounded-lg border-2 border-amber-300 bg-amber-50 p-3">
      <p className="text-xs font-semibold text-amber-800 mb-2">
        ⚠ Action requires approval: {action.message}
      </p>
      <button
        onClick={() => onApprove(action)}
        className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 transition-all shadow-md"
      >
        ✓ Approve & Execute
      </button>
    </div>
  )
}

/* ─── File upload zone ───────────────────────────────────────────────── */
function FileUpload({ onUpload }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)

  const handleFiles = async (files) => {
    if (!files.length) return
    setUploading(true)
    setResult(null)
    const file = files[0]
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await client.post('/assistant/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult({ success: true, message: `Uploaded "${file.name}" — ${data.rows || 0} rows processed.` })
      if (onUpload) onUpload(data)
    } catch (e) {
      setResult({ success: false, message: apiError(e) })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-4 text-center transition-all ${
        dragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:border-indigo-400 hover:bg-slate-50'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv,.pdf,.docx"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {uploading ? (
        <p className="text-xs text-slate-500">Uploading...</p>
      ) : (
        <p className="text-xs text-slate-500">
          📎 Drop a file here or click to upload (Excel, CSV, PDF, Word)
        </p>
      )}
      {result && (
        <p className={`mt-2 text-xs font-medium ${result.success ? 'text-emerald-600' : 'text-red-600'}`}>
          {result.message}
        </p>
      )}
    </div>
  )
}

/* ─── Chat message bubble ────────────────────────────────────────────── */
function MessageBubble({ msg, isUser }) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
        isUser
          ? 'bg-indigo-600 text-white rounded-br-md'
          : 'bg-white border border-slate-200 text-slate-800 rounded-bl-md shadow-sm'
      }`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] font-semibold uppercase tracking-wide opacity-60">
            {isUser ? 'You' : 'AI Assistant'}
          </span>
        </div>
        <div className={isUser ? 'text-white' : 'text-slate-700'}>
          {renderText(msg.content)}
        </div>
      </div>
    </div>
  )
}

/* ─── Main AI Assistant Page ─────────────────────────────────────────── */
export default function DataAnalysisAI() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hello! I'm the **Wellness Centre AI Assistant**. I can help you analyze counselling data, compare periods, detect trends, and generate reports.

Here are some things you can ask me:
- **Show all periods** — list available reporting windows
- **KPI summary** — key metrics for a specific period
- **Compare teams** — WC vs Team A vs YourDost vs Myndwell
- **Top concerns** — what issues students face most
- **Monthly trends** — case volume over time
- **Anomalies** — detect unusual spikes or drops
- **Generate reports** — create PPTX or Excel files

You can also upload files for me to analyze, or use the quick action buttons below.`,
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingAction, setPendingAction] = useState(null)
  const chatEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return
    const userMsg = { role: 'user', content: text.trim() }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setLoading(true)

    try {
      const payload = newMessages.map(m => ({ role: m.role, content: m.content }))
      const { data } = await client.post('/assistant/chat', { messages: payload })

      const assistantMsg = { role: 'assistant', content: data.reply, toolResults: data.tool_results || [] }
      setMessages(prev => [...prev, assistantMsg])

      if (data.pending_action) {
        setPendingAction(data.pending_action)
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${apiError(e)}`,
      }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleApprove = async (action) => {
    try {
      const { data, headers } = await client.put('/assistant/chat', { action }, { responseType: 'blob' })
      const blob = new Blob([data])
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = headers['content-disposition']?.match(/filename="?([^";]+)"?/)?.[1] || 'report.pptx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '✓ Report generated and downloaded successfully!',
      }])
      setPendingAction(null)
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Report generation failed: ${apiError(e)}`,
      }])
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="shrink-0 rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 p-5 text-white shadow-xl mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center text-xl">
            🤖
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight">AI Assistant</h1>
            <p className="text-[11px] text-slate-300">
              Ask questions about your wellness data, analyze trends, and generate reports
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <FileUpload />
          </div>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 min-h-0 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-1">
        {messages.map((msg, i) => (
          <div key={i}>
            <MessageBubble msg={msg} isUser={msg.role === 'user'} />
            {/* Tool results */}
            {msg.toolResults?.map((tr, j) => (
              <ToolResultCard key={j} tr={tr} />
            ))}
          </div>
        ))}
        {loading && (
          <div className="flex justify-start mb-3">
            <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs text-slate-400">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Pending approval */}
      {pendingAction && <ApprovalButton action={pendingAction} onApprove={handleApprove} />}

      {/* Quick actions */}
      <div className="shrink-0 mt-3 flex flex-wrap gap-1.5">
        {QUICK_ACTIONS.map((qa, i) => (
          <button
            key={i}
            onClick={() => sendMessage(qa.msg)}
            disabled={loading}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-medium text-slate-600 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-40 transition-all"
          >
            {qa.label}
          </button>
        ))}
      </div>

      {/* Input area */}
      <div className="shrink-0 mt-3 flex items-end gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your wellness data..."
          rows={1}
          className="flex-1 resize-none rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all shadow-sm"
          style={{ minHeight: '42px', maxHeight: '120px' }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || loading}
          className="shrink-0 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-indigo-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-1.5"
        >
          {loading ? (
            <span className="animate-spin">⏳</span>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          )}
          Send
        </button>
      </div>
    </div>
  )
}
