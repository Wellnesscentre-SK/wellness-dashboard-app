export function StatusBadge({ status }) {
  const styles = {
    complete: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    incomplete: 'bg-red-50 text-red-700 border-red-200',
    needs_review: 'bg-amber-50 text-amber-700 border-amber-200',
  }
  const labels = { complete: 'Complete', incomplete: 'Incomplete', needs_review: 'Needs review' }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${styles[status] || 'bg-slate-100 text-slate-600 border-slate-200'}`}
    >
      {labels[status] || status}
    </span>
  )
}

export function Card({ title, subtitle, action, children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 shadow-sm ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between px-5 pt-4 pb-1">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  )
}

export function Kpi({ label, value, accent, sub }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-2 text-3xl font-bold ${accent || 'text-slate-900'}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="py-16 text-center text-sm text-slate-500">
      <div className="mx-auto mb-3 h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      {label}
    </div>
  )
}

export function ErrorBox({ message }) {
  if (!message) return null
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{message}</div>
  )
}
