import { useCallback, useRef, useState } from 'react'
import client, { apiError } from '../api/client'
import { Card, ErrorBox, Spinner, StatusBadge } from '../components/ui'

const statusStyle = {
  ready: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  rejected: 'bg-red-50 text-red-700',
}

function CheckList({ checks }) {
  if (!checks?.length) return null
  return (
    <div className="mt-2 space-y-1 text-xs">
      {checks.map((c) => (
        <div key={c.name} className={c.passed ? 'text-emerald-600' : 'text-red-600'}>
          {c.passed ? '✓' : '✗'} {c.name}
          {!c.passed && (
            <span className="text-slate-500">
              {' '}
              (expected {c.expected}, got {c.actual})
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

export default function Import() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const inputRef = useRef(null)

  const onFileChange = (e) => {
    setFile(e.target.files[0] || null)
    setPreview(null)
    setResult(null)
    setError('')
  }

  const previewFile = useCallback(async () => {
    if (!file) return
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await client.post('/imports/preview', form)
      setPreview(data)
    } catch (err) {
      setError(apiError(err))
      setPreview(null)
    } finally {
      setBusy(false)
    }
  }, [file])

  const confirm = useCallback(
    async (replace = false) => {
      if (!preview) return
      setConfirming(true)
      setError('')
      try {
        const { data } = await client.post('/imports/confirm', {
          preview_id: preview.preview_id,
          replace,
        })
        setResult(data)
        setPreview(null)
        setFile(null)
        if (inputRef.current) inputRef.current.value = ''
      } catch (err) {
        setError(apiError(err))
      } finally {
        setConfirming(false)
      }
    },
    [preview],
  )

  const hasProblems = preview && preview.counts.rejected > 0

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Import Report</h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload the same weekly / monthly Excel file your team already fills in. No format changes needed.
        </p>
      </div>

      <Card>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls"
            onChange={onFileChange}
            className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
          />
          <button
            onClick={previewFile}
            disabled={!file || busy}
            className="shrink-0 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy ? 'Parsing…' : 'Preview & Validate'}
          </button>
        </div>
        {error && <div className="mt-4"><ErrorBox message={error} /></div>}
      </Card>

      {busy && <Spinner label="Parsing workbook…" />}

      {preview && !busy && (
        <Card
          title="Validation result"
          subtitle={preview.meta.title}
          action={
            <div className="flex gap-2">
              <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                {preview.counts.ready} ready
              </span>
              <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                {preview.counts.warned} warnings
              </span>
              <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                {preview.counts.rejected} rejected
              </span>
            </div>
          }
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-xs uppercase text-slate-400">Type</div>
              <div className="font-medium capitalize">{preview.meta.report_type}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-400">Period</div>
              <div className="font-medium">
                {preview.meta.period_start} → {preview.meta.period_end}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-400">Title vs period</div>
              <div className={`font-medium ${preview.meta.title_range_mismatch ? 'text-amber-600' : 'text-emerald-600'}`}>
                {preview.meta.title_range_mismatch ? 'Mismatch' : 'Matches'}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-400">Source totals</div>
              <div className="font-medium">
                New {Object.values(preview.vertical_totals.new).reduce((sum, value) => sum + (Number(value) || 0), 0)} ·
                FU {Object.values(preview.vertical_totals.followup).reduce((sum, value) => sum + (Number(value) || 0), 0)}
              </div>
            </div>
          </div>

          {preview.meta.title_range_mismatch && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              The title says one date range but the data reads another. Double-check before confirming.
            </div>
          )}

          {preview.duplicate && (
            <div className="mt-4 rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-800">
              A report for this exact period already exists (
              {preview.duplicate.label} · {preview.duplicate.status}). Confirming will ask you to replace it.
            </div>
          )}

          {hasProblems && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              Some rows were rejected. The import will be marked <b>incomplete</b>. Rows that failed validation
              are excluded from the merged data.
            </div>
          )}

          <div className="mt-5 overflow-hidden rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Case type</th>
                  <th className="px-4 py-2.5">Sub-team</th>
                  <th className="px-4 py-2.5">Row</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {preview.rows.map((r) => (
                  <tr key={`${r.sub_team}-${r.case_type}`}>
                    <td className="px-4 py-2.5 capitalize text-slate-700">{r.case_type}</td>
                    <td className="px-4 py-2.5 text-slate-900">{r.sub_team}</td>
                    <td className="px-4 py-2.5 text-slate-500">{r.sheet_row}</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusStyle[r.status]}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">
                      {r.reason}
                      {r.status !== 'ready' && <CheckList checks={r.checks} />}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button
              onClick={() => confirm(false)}
              disabled={confirming || preview.counts.rejected > 0 || !!preview.duplicate}
              className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40"
            >
              {confirming ? 'Importing…' : 'Confirm import'}
            </button>
            {preview.duplicate && (
              <button
                onClick={() => confirm(true)}
                disabled={confirming || preview.counts.rejected > 0}
                className="rounded-lg border border-orange-300 bg-orange-50 px-5 py-2.5 text-sm font-semibold text-orange-700 hover:bg-orange-100 disabled:opacity-40"
              >
                Replace existing period
              </button>
            )}
            {hasProblems && !preview.duplicate && (
              <button
                onClick={() => confirm(true)}
                disabled={confirming}
                className="rounded-lg border border-red-300 bg-red-50 px-5 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-40"
              >
                Import anyway (incomplete)
              </button>
            )}
            {preview.duplicate && preview.counts.rejected > 0 && (
              <button
                onClick={() => confirm(true)}
                disabled={confirming}
                className="rounded-lg border border-red-300 bg-red-50 px-5 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-40"
              >
                Replace & import (incomplete)
              </button>
            )}
            <button
              onClick={() => {
                setPreview(null)
                setFile(null)
                if (inputRef.current) inputRef.current.value = ''
              }}
              disabled={confirming}
              className="rounded-lg px-5 py-2.5 text-sm font-medium text-slate-500 hover:bg-slate-100"
            >
              Cancel
            </button>
          </div>
        </Card>
      )}

      {result && (
        <Card
          title="Import complete"
          action={<StatusBadge status={result.status} />}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-xs uppercase text-slate-400">Period</div>
              <div className="font-medium">{result.period_start} → {result.period_end}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-400">Rows imported</div>
              <div className="font-medium">{result.rows_imported}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-400">Warnings</div>
              <div className="font-medium">{result.rows_warned}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-slate-400">Rejected</div>
              <div className="font-medium">{result.rows_rejected}</div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
