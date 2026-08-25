import { useEffect, useState } from 'react'
import client, { apiError, generateReport } from '../api/client'
import { Card, Spinner, StatusBadge } from '../components/ui'

export default function Periods() {
  const [periods, setPeriods] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [exporting, setExporting] = useState(null)
  const [exportError, setExportError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (typeFilter) params.set('report_type', typeFilter)
    if (statusFilter) params.set('status', statusFilter)
    client
      .get(`/periods?${params.toString()}`)
      .then(({ data }) => setPeriods(data))
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [typeFilter, statusFilter])

  const onExport = async (p, format) => {
    setExporting({ id: p.id, format })
    setExportError('')
    try {
      await generateReport(p.id, format)
    } catch (e) {
      setExportError(`Failed to export ${p.report_type} report: ${apiError(e)}`)
    } finally {
      setExporting(null)
    }
  }

  const onDeleteConfirmed = async () => {
    if (!confirmDelete) return
    setDeleting(true)
    setDeleteError('')
    try {
      await client.delete(`/periods/${confirmDelete.id}`)
      setConfirmDelete(null)
      load()
    } catch (e) {
      setDeleteError(`Failed to delete report #${confirmDelete.id}: ${apiError(e)}`)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Periods</h1>
          <p className="text-sm text-slate-500 mt-1">All active reporting periods (superseded versions are hidden).</p>
        </div>
        <div className="flex gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white"
          >
            <option value="">All types</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white"
          >
            <option value="">All statuses</option>
            <option value="complete">Complete</option>
            <option value="incomplete">Incomplete</option>
            <option value="needs_review">Needs review</option>
          </select>
        </div>
      </div>

      {loading && <Spinner />}
      {error && <div className="text-sm text-red-600">{error}</div>}
      {!loading && !periods.length && (
        <Card><p className="text-sm text-slate-600">No periods match the current filters.</p></Card>
      )}

      {!loading && periods.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-5 py-3">ID</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Period</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Source</th>
                <th className="px-5 py-3">Case rows</th>
                <th className="px-5 py-3 text-right">Reports</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {periods.map((p) => {
                const total = p.case_rows.reduce((acc, r) => acc + r.total_cases, 0)
                const busy = exporting?.id === p.id
                return (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 text-slate-400">#{p.id}</td>
                    <td className="px-5 py-3 capitalize text-slate-700">{p.report_type}</td>
                    <td className="px-5 py-3 text-slate-900">{p.period_start} to {p.period_end}</td>
                    <td className="px-5 py-3"><StatusBadge status={p.status} /></td>
                    <td className="px-5 py-3 text-slate-600">{p.source}</td>
                    <td className="px-5 py-3 font-medium text-slate-900">{total}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => onExport(p, 'ppt')}
                          disabled={busy}
                          className="rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                        >
                          {busy && exporting?.format === 'ppt' ? 'Building…' : 'PPT'}
                        </button>
                        <button
                          onClick={() => onExport(p, 'xlsx')}
                          disabled={busy}
                          className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          {busy && exporting?.format === 'xlsx' ? '…' : 'XLSX'}
                        </button>
                        <button
                          onClick={() => onExport(p, 'csv')}
                          disabled={busy}
                          className="rounded-md bg-slate-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                        >
                          {busy && exporting?.format === 'csv' ? '…' : 'CSV'}
                        </button>
                        <button
                          onClick={() => onExport(p, 'pdf')}
                          disabled={busy}
                          className="rounded-md bg-rose-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50"
                        >
                          {busy && exporting?.format === 'pdf' ? '…' : 'PDF'}
                        </button>
                        <button
                          onClick={() => { setDeleteError(''); setConfirmDelete(p) }}
                          className="rounded-md border border-rose-300 bg-white px-2.5 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50"
                          title={`Delete report #${p.id} and all its data`}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}
      {exportError && <div className="text-sm text-red-600">{exportError}</div>}

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border border-rose-200">
            <div className="flex items-center gap-2 text-rose-700 font-bold text-base border-b border-rose-100 pb-3">
              Delete this entire report?
            </div>
            <div className="py-4 space-y-2 text-sm text-slate-700">
              <p>
                Report <span className="font-semibold">#{confirmDelete.id}</span> —{' '}
                <span className="capitalize font-medium">{confirmDelete.report_type}</span>,{' '}
                {confirmDelete.period_start} to {confirmDelete.period_end}
              </p>
              <p className="text-slate-500">
                This permanently removes the report with all its case rows, worksheet entries,
                metrics and import history. This cannot be undone.
              </p>
            </div>
            {deleteError && <div className="pb-3 text-sm text-red-600">{deleteError}</div>}
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setConfirmDelete(null)}
                disabled={deleting}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => onDeleteConfirmed()}
                disabled={deleting}
                className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
              >
                {deleting ? 'Deleting…' : 'Delete Report'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
