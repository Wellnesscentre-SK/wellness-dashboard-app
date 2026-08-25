import { useEffect, useState } from 'react'
import client, { apiError } from '../api/client'
import { Card, Spinner, StatusBadge } from '../components/ui'

export default function ImportHistory() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')

  const load = () => {
    setLoading(true)
    client
      .get(`/imports/history${q ? `?q=${encodeURIComponent(q)}` : ''}`)
      .then(({ data }) => setItems(data))
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [q])

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Import History</h1>
          <p className="text-sm text-slate-500 mt-1">Every upload and its outcome.</p>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search filename, user, type…"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm w-64 bg-white"
        />
      </div>

      {loading && <Spinner />}
      {error && <div className="text-sm text-red-600">{error}</div>}
      {!loading && !items.length && (
        <Card><p className="text-sm text-slate-600">No imports recorded yet.</p></Card>
      )}

      {!loading && items.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-5 py-3">Imported</th>
                <th className="px-5 py-3">Filename</th>
                <th className="px-5 py-3">Period</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3 text-right">Rows</th>
                <th className="px-5 py-3 text-right">Warned</th>
                <th className="px-5 py-3 text-right">Rejected</th>
                <th className="px-5 py-3">By</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((it) => (
                <tr key={it.id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 text-slate-500 whitespace-nowrap">
                    {new Date(it.imported_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-slate-900 max-w-52 truncate">{it.original_filename}</td>
                  <td className="px-5 py-3 text-slate-600">{it.period_label}</td>
                  <td className="px-5 py-3"><StatusBadge status={it.status} /></td>
                  <td className="px-5 py-3 text-right font-medium">{it.rows_imported}</td>
                  <td className="px-5 py-3 text-right">{it.rows_warned}</td>
                  <td className="px-5 py-3 text-right text-red-600">{it.rows_rejected}</td>
                  <td className="px-5 py-3 text-slate-600">{it.imported_by_name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
