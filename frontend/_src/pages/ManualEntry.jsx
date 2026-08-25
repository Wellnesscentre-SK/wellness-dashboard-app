import { useEffect, useMemo, useState, useRef } from 'react'
import client, { apiError } from '../api/client'
import { Card, ErrorBox, Spinner, StatusBadge } from '../components/ui'
import CompareAnalysis from '../components/CompareAnalysis'

const TEAMS = ['WLN Ctr', 'Team A', 'Your Dost', 'Myndwell']
const CASE_TYPES = ['new', 'followup']

// 29 Numeric columns divided into 5 groups
const GROUPS = [
  {
    key: 'gender',
    title: 'GENDER',
    headerBg: 'bg-sky-100 text-sky-900 border-sky-300',
    cellBg: 'bg-sky-50/40',
    columns: [
      { key: 'total_cases', label: 'Total Cases', isAuto: true },
      { key: 'gender_male', label: 'Male' },
      { key: 'gender_female', label: 'Female' },
      { key: 'gender_other', label: 'Others / Not to say' },
    ],
  },
  {
    key: 'mode',
    title: 'MODE OF SESSION',
    headerBg: 'bg-amber-100 text-amber-900 border-amber-300',
    cellBg: 'bg-amber-50/40',
    columns: [
      { key: 'mode_online', label: 'Online' },
      { key: 'mode_in_person', label: 'In person' },
      { key: 'mode_phone', label: 'Phone' },
    ],
  },
  {
    key: 'referral',
    title: 'REFERRAL TYPE',
    headerBg: 'bg-purple-100 text-purple-900 border-purple-300',
    cellBg: 'bg-purple-50/40',
    columns: [
      { key: 'referral_self', label: 'Self' },
      { key: 'referral_director', label: 'Director / Kushal Calls' },
      { key: 'referral_dean', label: 'Dean/HoD/Faculty/Insti Hosp' },
      { key: 'referral_friend', label: 'Friend/Family' },
      { key: 'referral_mitr', label: 'Mitr/Saathi' },
    ],
  },
  {
    key: 'concern',
    title: 'RANGE OF CONCERN ADDRESSED',
    headerBg: 'bg-rose-100 text-rose-900 border-rose-300',
    cellBg: 'bg-rose-50/40',
    columns: [
      { key: 'concern_anxiety', label: '1. Anxiety / Depression / Panic / OCD' },
      { key: 'concern_stress', label: '2. Acute Stress / Trauma' },
      { key: 'concern_career', label: '3. Career / Academic' },
      { key: 'concern_interpersonal', label: '4. Inter-personal' },
      { key: 'concern_self_dev', label: '5. Self Development' },
      { key: 'concern_clinical', label: '6. Clinical' },
      { key: 'concern_addiction', label: '7. Addiction' },
      { key: 'concern_medical', label: '8. Medical / Health issues' },
      { key: 'concern_suicidal', label: '9. Suicidal Ideation / Self-harm' },
    ],
  },
  {
    key: 'stakeholder',
    title: 'STAKEHOLDER',
    headerBg: 'bg-slate-200 text-slate-900 border-slate-400',
    cellBg: 'bg-slate-50/60',
    columns: [
      { key: 'stake_ug', label: '1. UG' },
      { key: 'stake_pg', label: '2. PG' },
      { key: 'stake_phd', label: '3. Ph.D' },
      { key: 'stake_dual', label: '4. Dual Degree' },
      { key: 'stake_faculty', label: '5. IIT Faculty / Staff' },
      { key: 'stake_employee_family', label: '6. Employee Family' },
      { key: 'stake_postdoc', label: '7. Post Doc / Project Associate' },
      { key: 'stake_unidentified', label: '8. Not Able to Identify' },
    ],
  },
]

const ALL_COLUMNS = GROUPS.flatMap((g) => g.columns)
const EDITABLE_COLUMNS = ALL_COLUMNS.filter((c) => !c.isAuto)

// ---- Calendar / date-range helpers -------------------------------------
function toISODate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function weekRange(offset) {
  const now = new Date()
  const diffToMonday = (now.getDay() + 6) % 7
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diffToMonday + offset * 7)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  return { start: toISODate(monday), end: toISODate(sunday) }
}

function monthRange(offset) {
  const now = new Date()
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  const last = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0)
  return { start: toISODate(first), end: toISODate(last) }
}

function yearRange(offset) {
  const y = new Date().getFullYear() + offset
  return { start: `${y}-01-01`, end: `${y}-12-31` }
}

const CALENDAR_PRESETS = [
  { label: 'This Week', range: () => weekRange(0) },
  { label: 'Last Week', range: () => weekRange(-1) },
  { label: 'This Month', range: () => monthRange(0) },
  { label: 'Last Month', range: () => monthRange(-1) },
  { label: 'This Year', range: () => yearRange(0) },
  { label: 'Last Year', range: () => yearRange(-1) },
]

function emptyRowPayload() {
  const p = {}
  ALL_COLUMNS.forEach((c) => {
    p[c.key] = 0
  })
  return p
}

function emptySheetState() {
  const state = {}
  CASE_TYPES.forEach((ct) => {
    TEAMS.forEach((team) => {
      state[`${ct}_${team}`] = emptyRowPayload()
    })
  })
  return state
}

export default function ManualEntry() {
  const [periods, setPeriods] = useState([])
  const [selectedPeriodId, setSelectedPeriodId] = useState('')
  const [activeTab, setActiveTab] = useState('worksheet') // 'worksheet' | 'verification' | 'audit'
  const [sheetData, setSheetData] = useState(() => emptySheetState())
  const [resetNonce, setResetNonce] = useState(0)
  const [worksheetNonce, setWorksheetNonce] = useState(0)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [auditLogs, setAuditLogs] = useState([])
  const [rangeStart, setRangeStart] = useState('')
  const [rangeEnd, setRangeEnd] = useState('')
  const [calendarMatched, setCalendarMatched] = useState(null)
  const [periodForm, setPeriodForm] = useState({
    report_type: 'weekly',
    period_start: '',
    period_end: '',
    status: 'complete',
    source: 'manual',
    title: '',
  })
  const [editingPeriodId, setEditingPeriodId] = useState(null)
  const [periodSaving, setPeriodSaving] = useState(false)

  // Modal State for Verification Failure Detail
  const [verificationModal, setVerificationModal] = useState(null)
  // Modal State for Generate PPT Pre-flight Check
  const [pptWarningModal, setPptWarningModal] = useState(null)
  // Modal State for Save With Validation Warnings
  const [saveWarningModal, setSaveWarningModal] = useState(false)
  // Import-file-into-worksheet flow
  const [importPreview, setImportPreview] = useState(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importReplaceConfirm, setImportReplaceConfirm] = useState(false)
  const importInputRef = useRef(null)

  // Cell Navigation focus ref
  const inputRefs = useRef({})
  const activeInputKey = useRef(null)

  // Load periods list
  const loadPeriods = () => {
    client
      .get('/periods')
      .then(({ data }) => {
        setPeriods(data)
        if (data.length === 0) {
          setSelectedPeriodId('')
          return
        }
        setSelectedPeriodId((cur) => {
          if (data.some((p) => String(p.id) === cur)) return cur
          return String(data[0].id)
        })
      })
      .catch((e) => setError(apiError(e)))
  }

  useEffect(loadPeriods, [])

  // Load worksheet data for selected period (worksheetNonce forces a reload,
  // e.g. after an import replaces the currently-selected period)
  useEffect(() => {
    if (!selectedPeriodId) return
    setLoading(true)
    setError('')

    client
      .get(`/periods/${selectedPeriodId}/worksheet`)
      .then(({ data }) => {
        const nextState = emptySheetState()
        data.raw_rows.forEach((r) => {
          const key = `${r.case_type}_${r.sub_team}`
          if (nextState[key]) {
            const cleanPayload = { ...r.raw_payload }
            // Ensure Total Cases is auto-derived
            cleanPayload.total_cases =
              (cleanPayload.gender_male || 0) +
              (cleanPayload.gender_female || 0) +
              (cleanPayload.gender_other || 0)
            nextState[key] = cleanPayload
          }
        })
        setSheetData(nextState)
        setAuditLogs(data.audit_logs || [])
        setHasUnsavedChanges(false)
      })
      .catch((e) => setError(apiError(e)))
      .finally(() => setLoading(false))
  }, [selectedPeriodId, worksheetNonce])

  // Calculate full calculated sheet (subteams + totals + grand total)
  const calculatedSheet = useMemo(() => {
    const full = { ...sheetData }

    // Recompute total_cases for all editable subteam rows
    CASE_TYPES.forEach((ct) => {
      TEAMS.forEach((team) => {
        const k = `${ct}_${team}`
        const row = full[k] ? { ...full[k] } : emptyRowPayload()
        row.total_cases =
          (Number(row.gender_male) || 0) +
          (Number(row.gender_female) || 0) +
          (Number(row.gender_other) || 0)
        full[k] = row
      })
    })

    // Compute TOTAL NEW row
    const totalNew = emptyRowPayload()
    ALL_COLUMNS.forEach((col) => {
      totalNew[col.key] = TEAMS.reduce((sum, team) => sum + (Number(full[`new_${team}`]?.[col.key]) || 0), 0)
    })
    full.total_new = totalNew

    // Compute TOTAL FOLLOW-UP row
    const totalFollowup = emptyRowPayload()
    ALL_COLUMNS.forEach((col) => {
      totalFollowup[col.key] = TEAMS.reduce(
        (sum, team) => sum + (Number(full[`followup_${team}`]?.[col.key]) || 0),
        0,
      )
    })
    full.total_followup = totalFollowup

    // Compute GRAND TOTAL row
    const grandTotal = emptyRowPayload()
    ALL_COLUMNS.forEach((col) => {
      grandTotal[col.key] = totalNew[col.key] + totalFollowup[col.key]
    })
    full.grand_total = grandTotal

    return full
  }, [sheetData])

  // Verification calculations for all 11 rows across all 5 checks
  const verificationResults = useMemo(() => {
    const rows = []

    const rowDefs = [
      { id: 'new_WLN Ctr', label: 'New — WLN Ctr', key: 'new_WLN Ctr' },
      { id: 'new_Team A', label: 'New — Team A', key: 'new_Team A' },
      { id: 'new_Your Dost', label: 'New — Your Dost', key: 'new_Your Dost' },
      { id: 'new_Myndwell', label: 'New — Myndwell', key: 'new_Myndwell' },
      { id: 'total_new', label: 'Total New', key: 'total_new', isTotal: true },
      { id: 'followup_WLN Ctr', label: 'Follow-up — WLN Ctr', key: 'followup_WLN Ctr' },
      { id: 'followup_Team A', label: 'Follow-up — Team A', key: 'followup_Team A' },
      { id: 'followup_Your Dost', label: 'Follow-up — Your Dost', key: 'followup_Your Dost' },
      { id: 'followup_Myndwell', label: 'Follow-up — Myndwell', key: 'followup_Myndwell' },
      { id: 'total_followup', label: 'Total Follow-up', key: 'total_followup', isTotal: true },
      { id: 'grand_total', label: 'Grand Total', key: 'grand_total', isGrandTotal: true },
    ]

    rowDefs.forEach((def) => {
      const payload = calculatedSheet[def.key] || emptyRowPayload()
      const totalCases = payload.total_cases || 0

      // 1. Gender Verification
      const genderSum =
        (Number(payload.gender_male) || 0) +
        (Number(payload.gender_female) || 0) +
        (Number(payload.gender_other) || 0)
      const genderValid = genderSum === totalCases

      // 2. Session Verification
      const sessionSum =
        (Number(payload.mode_online) || 0) +
        (Number(payload.mode_in_person) || 0) +
        (Number(payload.mode_phone) || 0)
      const sessionValid = sessionSum === totalCases

      // 3. Referral Verification
      const referralSum =
        (Number(payload.referral_self) || 0) +
        (Number(payload.referral_director) || 0) +
        (Number(payload.referral_dean) || 0) +
        (Number(payload.referral_friend) || 0) +
        (Number(payload.referral_mitr) || 0)
      const referralValid = referralSum === totalCases

      // 4. Concern Verification
      const concernSum = [
        'concern_anxiety',
        'concern_stress',
        'concern_career',
        'concern_interpersonal',
        'concern_self_dev',
        'concern_clinical',
        'concern_addiction',
        'concern_medical',
        'concern_suicidal',
      ].reduce((s, k) => s + (Number(payload[k]) || 0), 0)
      const concernValid = concernSum === totalCases

      // 5. Stakeholder Verification
      const stakeholderSum = [
        'stake_ug',
        'stake_pg',
        'stake_phd',
        'stake_dual',
        'stake_faculty',
        'stake_employee_family',
        'stake_postdoc',
        'stake_unidentified',
      ].reduce((s, k) => s + (Number(payload[k]) || 0), 0)
      const stakeholderValid = stakeholderSum === totalCases

      rows.push({
        ...def,
        totalCases,
        checks: {
          gender: { passed: genderValid, expected: totalCases, actual: genderSum, label: 'Gender' },
          session: { passed: sessionValid, expected: totalCases, actual: sessionSum, label: 'Mode of Session' },
          referral: { passed: referralValid, expected: totalCases, actual: referralSum, label: 'Referral Type' },
          concern: { passed: concernValid, expected: totalCases, actual: concernSum, label: 'Range of Concern Addressed' },
          stakeholder: { passed: stakeholderValid, expected: totalCases, actual: stakeholderSum, label: 'Stakeholder' },
        },
      })
    })

    const totalFailed = rows.reduce((sum, r) => {
      return sum + Object.values(r.checks).filter((c) => !c.passed).length
    }, 0)

    return { rows, totalFailed, isAllValid: totalFailed === 0 }
  }, [calculatedSheet])

  // Cell editing handler. The inputs are UNCONTROLLED so the browser owns
  // the typed text (multi-digit entries like 12 / 345 can never be
  // clobbered by a re-render); on every keystroke we parse the raw value
  // into sheetData for live totals and commit it on blur.
  const handleCellChange = (caseType, team, colKey, rawValue) => {
    let numVal = rawValue.replace(/[^0-9]/g, '')
    if (numVal === '') numVal = '0'
    const cleanNum = Math.max(0, parseInt(numVal, 10) || 0)

    const key = `${caseType}_${team}`
    setSheetData((prev) => {
      const row = { ...(prev[key] || emptyRowPayload()) }
      row[colKey] = cleanNum
      // Auto-recalculate Total Cases from Gender
      row.total_cases = (row.gender_male || 0) + (row.gender_female || 0) + (row.gender_other || 0)
      return { ...prev, [key]: row }
    })
    setHasUnsavedChanges(true)
    setSuccessMsg('')
  }

  const commitCell = (e) => {
    // Normalize the displayed value (e.g. "007" -> "7") once the user
    // leaves the cell. The parsed number is already stored in sheetData.
    const val = e.target.value
    const num = parseInt(val, 10)
    if (isNaN(num) || num < 0) {
      e.target.value = ''
    } else {
      e.target.value = String(num)
    }
  }

  const selectedPeriod = periods.find((p) => String(p.id) === selectedPeriodId)

  const findPeriodForRange = (start, end) => {
    const exact = periods.find((p) => p.period_start === start && p.period_end === end)
    if (exact) return exact
    return periods
      .filter((p) => p.period_start <= start && p.period_end >= end)
      .sort((a, b) => {
        const spanA = new Date(a.period_end) - new Date(a.period_start)
        const spanB = new Date(b.period_end) - new Date(b.period_start)
        return spanA - spanB
      })[0] || null
  }

  const handlePeriodSelect = (e) => {
    const id = e.target.value
    setSelectedPeriodId(id)
    const p = periods.find((x) => String(x.id) === id)
    if (p) {
      setRangeStart(p.period_start)
      setRangeEnd(p.period_end)
      setCalendarMatched(p)
    }
  }

  const applyCalendarRange = () => {
    setError('')
    setSuccessMsg('')
    if (!rangeStart || !rangeEnd) {
      setError('Please pick both a start and end date in the calendar.')
      return
    }
    if (rangeStart > rangeEnd) {
      setError('Start date must be on or before the end date.')
      return
    }
    const match = findPeriodForRange(rangeStart, rangeEnd)
    if (!match) {
      setCalendarMatched(null)
      setError(
        `No reporting period covers ${rangeStart} to ${rangeEnd}. Import a file for this range or pick a different range.`,
      )
      return
    }
    setSelectedPeriodId(String(match.id))
    setCalendarMatched(match)
  }

  const resetCalendar = () => {
    setRangeStart('')
    setRangeEnd('')
    setCalendarMatched(null)
    if (periods.length > 0) setSelectedPeriodId(String(periods[0].id))
    setError('')
    setSuccessMsg('')
  }

  const resetWorksheet = () => {
    if (!window.confirm('Reset all cells in this worksheet to 0? Unsaved entries will be lost.')) return
    setSheetData(emptySheetState())
    setResetNonce((n) => n + 1)
    setHasUnsavedChanges(true)
    setSuccessMsg('')
    setError('')
  }

  const resetPeriodForm = () => {
    setPeriodForm({
      report_type: 'weekly',
      period_start: '',
      period_end: '',
      status: 'complete',
      source: 'manual',
      title: '',
    })
    setEditingPeriodId(null)
  }

  const startEditPeriod = (p) => {
    setPeriodForm({
      report_type: p.report_type,
      period_start: p.period_start,
      period_end: p.period_end,
      status: p.status,
      source: p.source,
      title: p.title || '',
    })
    setEditingPeriodId(p.id)
  }

  const savePeriod = async (e) => {
    e.preventDefault()
    setPeriodSaving(true)
    setError('')
    setSuccessMsg('')
    try {
      if (editingPeriodId) {
        await client.patch(`/periods/${editingPeriodId}`, periodForm)
        setSuccessMsg('Period updated successfully!')
      } else {
        const { data } = await client.post('/periods', periodForm)
        setSelectedPeriodId(String(data.id))
        setRangeStart(data.period_start)
        setRangeEnd(data.period_end)
        setCalendarMatched(data)
        setSuccessMsg('New period created! Enter its numbers below or import a file for it.')
      }
      resetPeriodForm()
      await loadPeriods()
    } catch (err) {
      setError(apiError(err))
    } finally {
      setPeriodSaving(false)
    }
  }

  const deletePeriod = async (p) => {
    if (
      !window.confirm(
        `Delete ${p.report_type.toUpperCase()} period ${p.period_start} to ${p.period_end}? All of its worksheet data and imports will be removed.`,
      )
    ) {
      return
    }
    try {
      await client.delete(`/periods/${p.id}`)
      await loadPeriods()
      setError('')
      setSuccessMsg('Period deleted.')
    } catch (err) {
      setError(apiError(err))
    }
  }

  // Save full worksheet to backend
  const handleSaveWorksheet = async (force = false) => {
    if (!selectedPeriodId) return
    setSaving(true)
    setError('')
    setSuccessMsg('')

    const payloadRows = []
    CASE_TYPES.forEach((ct) => {
      TEAMS.forEach((t) => {
        const k = `${ct}_${t}`
        payloadRows.push({
          case_type: ct,
          sub_team: t,
          columns: sheetData[k] || emptyRowPayload(),
        })
      })
    })

    try {
      await client.post(`/periods/${selectedPeriodId}/worksheet`, {
        rows: payloadRows,
        force_save_with_warnings: force,
      })
      setHasUnsavedChanges(false)
      setSuccessMsg('Worksheet saved successfully!')

      // Refresh audit logs
      const { data } = await client.get(`/periods/${selectedPeriodId}/worksheet`)
      setAuditLogs(data.audit_logs || [])
    } catch (err) {
      const code = err?.response?.data?.error
      if (code === 'ROW_VALIDATION_FAILED' && !force) {
        setSaveWarningModal(true)
      }
      setError(apiError(err))
    } finally {
      setSaving(false)
    }
  }

  // ===== Import file directly into the worksheet =====
  const handleImportFileChange = (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-selecting the same file
    if (!file) return
    setImportBusy(true)
    setError('')
    setSuccessMsg('')

    const fd = new FormData()
    fd.append('file', file)
    client
      .post('/imports/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      .then(({ data }) => setImportPreview(data))
      .catch((err) => setError(apiError(err)))
      .finally(() => setImportBusy(false))
  }

  const confirmImportIntoWorksheet = (replace = false) => {
    if (!importPreview?.preview_id) return
    setImportBusy(true)
    setError('')
    setSuccessMsg('')

    client
      .post('/imports/confirm', { preview_id: importPreview.preview_id, replace })
      .then(({ data }) => {
        setImportPreview(null)
        setImportReplaceConfirm(false)
        loadPeriods()
        setSelectedPeriodId(String(data.period_id))
        setWorksheetNonce((n) => n + 1)
        setSuccessMsg(
          `Imported "${data.report_type.toUpperCase()}" (${data.period_start} to ${data.period_end}) — loaded into the worksheet below.`,
        )
      })
      .catch((err) => {
        const code = err?.response?.data?.error
        if (code === 'DUPLICATE_PERIOD') {
          setImportReplaceConfirm(true)
        } else {
          setImportPreview(null)
          setImportReplaceConfirm(false)
          setError(apiError(err))
        }
      })
      .finally(() => setImportBusy(false))
  }

  const closeImportModal = () => {
    if (importBusy) return
    setImportPreview(null)
    setImportReplaceConfirm(false)
  }

  // Handle Generate PPT action with verification warning pre-flight
  const handleGeneratePPTClick = () => {
    if (!verificationResults.isAllValid) {
      setPptWarningModal({
        failedCount: verificationResults.totalFailed,
      })
    } else {
      executeGeneratePPT()
    }
  }

  const executeGeneratePPT = async () => {
    setPptWarningModal(null)
    setLoading(true)
    try {
      const response = await client.post(
        '/reports/generate',
        { period_id: selectedPeriodId, format: 'ppt' },
        { responseType: 'blob' },
      )
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Wellness_Report_Period_${selectedPeriodId}.pptx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setLoading(false)
    }
  }

  // Handle Annual (merged Jan-Dec) PPT action
  const handleGenerateAnnualPPT = async () => {
    if (!selectedPeriodId) return
    setLoading(true)
    try {
      const response = await client.post(
        '/reports/generate',
        { period_id: selectedPeriodId, format: 'annual_ppt' },
        { responseType: 'blob' },
      )
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      })
      const year = selectedPeriod ? selectedPeriod.period_start.slice(0, 4) : ''
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Annual_${year}_Data_Analysis.pptx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setLoading(false)
    }
  }

  // Handle Export Excel action
  const handleExportExcel = async () => {
    setLoading(true)
    try {
      const response = await client.post(
        '/reports/generate',
        { period_id: selectedPeriodId, format: 'xlsx' },
        { responseType: 'blob' },
      )
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `Wellness_Worksheet_Period_${selectedPeriodId}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(apiError(err))
    }
  }

  // Keyboard grid navigation (Arrow keys, Tab, Enter)
  const handleKeyDown = (e, rowIdx, colIdx) => {
    // Block non-numeric keys that type="number" still permits
    const blocked = ['e', 'E', '+', '-', '.', ',']
    if (blocked.includes(e.key)) {
      e.preventDefault()
      return
    }

    let nextRow = rowIdx
    let nextCol = colIdx

    if (e.key === 'ArrowRight' || (e.key === 'Tab' && !e.shiftKey)) {
      e.preventDefault()
      nextCol = colIdx < EDITABLE_COLUMNS.length - 1 ? colIdx + 1 : 0
      if (e.key === 'Tab' && nextCol === 0) nextRow = (rowIdx + 1) % 8
    } else if (e.key === 'ArrowLeft' || (e.key === 'Tab' && e.shiftKey)) {
      e.preventDefault()
      nextCol = colIdx > 0 ? colIdx - 1 : EDITABLE_COLUMNS.length - 1
      if (e.key === 'Tab' && nextCol === EDITABLE_COLUMNS.length - 1) nextRow = (rowIdx - 1 + 8) % 8
    } else if (e.key === 'ArrowDown' || (e.key === 'Enter' && !e.shiftKey)) {
      e.preventDefault()
      nextRow = (rowIdx + 1) % 8
    } else if (e.key === 'ArrowUp' || (e.key === 'Enter' && e.shiftKey)) {
      e.preventDefault()
      nextRow = (rowIdx - 1 + 8) % 8
    }

    const refKey = `${nextRow}_${nextCol}`
    if (inputRefs.current[refKey]) {
      inputRefs.current[refKey].focus()
      inputRefs.current[refKey].select()
    }
  }

  const handlePaste = (e) => {
    const text = (e.clipboardData || window.clipboardData).getData('text')
    if (!/^\d*$/.test(text)) {
      e.preventDefault()
    }
  }

  const handleNumpadInput = (digit) => {
    const el = activeInputKey.current && inputRefs.current[activeInputKey.current]
    if (!el) return
    el.focus()

    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set

    if (digit === 'CLEAR') {
      nativeSetter.call(el, '')
      el.dispatchEvent(new Event('input', { bubbles: true }))
      return
    }
    if (digit === 'BACKSPACE') {
      nativeSetter.call(el, (el.value || '').slice(0, -1))
      el.dispatchEvent(new Event('input', { bubbles: true }))
      return
    }

    const next = (el.value || '') + digit
    nativeSetter.call(el, next)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }

  // Render subteam editable rows and total rows
  const renderRowGroup = (caseType, sectionTitle) => {
    const isNew = caseType === 'new'
    const totalRowKey = isNew ? 'total_new' : 'total_followup'
    const totalLabel = isNew ? 'TOTAL NO. OF CASES NEW' : 'TOTAL NO. OF CASES FOLLOW-UP'

    return (
      <>
        {/* Section Header Row */}
        <tr className="bg-slate-800 text-white font-bold text-xs uppercase tracking-wider">
          <td className="sticky left-0 z-20 bg-slate-950 px-4 py-2 text-left border-r border-slate-700 shadow-md">
            {sectionTitle}
          </td>
          <td colSpan={ALL_COLUMNS.length} className="px-4 py-2 text-left text-slate-300">
            Enter numerical counts for each vertical below
          </td>
        </tr>

        {/* 4 Vertical Subteam Rows */}
        {TEAMS.map((team, tIdx) => {
          const rowKey = `${caseType}_${team}`
          const rowPayload = calculatedSheet[rowKey] || emptyRowPayload()
          const globalRowIdx = (isNew ? 0 : 4) + tIdx

          return (
            <tr key={rowKey} className="hover:bg-indigo-50/50 transition-colors border-b border-slate-200">
              <td className="sticky left-0 z-20 bg-white font-semibold text-slate-800 text-xs px-4 py-2 text-left border-r-2 border-slate-400 shadow-sm whitespace-nowrap">
                {team}
              </td>

              {GROUPS.map((group) =>
                group.columns.map((col) => {
                  const val = rowPayload[col.key] ?? 0
                  if (col.isAuto) {
                    return (
                      <td
                        key={col.key}
                        className="px-2 py-1.5 text-center font-bold text-slate-900 bg-slate-100 border-r border-slate-300 text-xs"
                      >
                        {val}
                      </td>
                    )
                  }

                  const editableIdx = EDITABLE_COLUMNS.findIndex((c) => c.key === col.key)
                  const refKey = `${globalRowIdx}_${editableIdx}`

                  return (
                    <td key={col.key} className={`p-1 border-r border-slate-200 min-w-[90px] ${group.cellBg}`}>
                      <input
                        key={`${selectedPeriodId}_${rowKey}_${col.key}_${resetNonce}`}
                        ref={(el) => (inputRefs.current[refKey] = el)}
                        type="number"
                        min="0"
                        step="1"
                        autoComplete="off"
                        defaultValue={val === 0 ? '' : val}
                        placeholder="0"
                        onChange={(e) => handleCellChange(caseType, team, col.key, e.target.value)}
                        onBlur={commitCell}
                        onFocus={(e) => { activeInputKey.current = refKey; e.target.select() }}
                        onKeyDown={(e) => handleKeyDown(e, globalRowIdx, editableIdx)}
                        onPaste={handlePaste}
                        className="w-full h-8 text-center text-xs font-medium text-slate-900 bg-white border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-all shadow-inner select-text [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                      />
                    </td>
                  )
                }),
              )}
            </tr>
          )
        })}

        {/* Section Total Row */}
        <tr className="bg-amber-200 font-extrabold text-xs text-amber-950 border-b-2 border-amber-400">
          <td className="sticky left-0 z-20 bg-amber-300 px-4 py-2.5 text-left border-r-2 border-amber-500 shadow-md whitespace-nowrap">
            {totalLabel}
          </td>
          {GROUPS.map((group) =>
            group.columns.map((col) => (
              <td key={col.key} className="px-2 py-2.5 text-center border-r border-amber-300 text-xs">
                {calculatedSheet[totalRowKey]?.[col.key] ?? 0}
              </td>
            )),
          )}
        </tr>
      </>
    )
  }

  return (
    <div className="max-w-[100vw] space-y-6">
      {/* Top Header Card */}
      <div className="rounded-3xl border border-slate-200 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 p-6 text-white shadow-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="rounded-full bg-indigo-500/20 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-indigo-300 border border-indigo-500/30">
                Reports → Manual
              </span>
              {hasUnsavedChanges ? (
                <span className="animate-pulse rounded-full bg-amber-500/20 px-3 py-1 text-xs font-semibold text-amber-300 border border-amber-500/40">
                  ● Unsaved changes
                </span>
              ) : (
                <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-300 border border-emerald-500/30">
                  ✓ Saved successfully
                </span>
              )}
            </div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
              Excel-Style Manual Data-Entry Worksheet
            </h1>
            <p className="mt-1 text-xs text-slate-300 max-w-2xl">
              Directly enter counts for NEW and FOLLOW-UP verticals. Formulas, totals, and verification rules reconcile in real time.
            </p>
          </div>

          {/* Period Selector & Primary Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Select Month / Period</label>
              <select
                value={selectedPeriodId}
                onChange={handlePeriodSelect}
                className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-white font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
              >
                {periods.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.report_type.toUpperCase()} ({p.period_start} to {p.period_end})
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => importInputRef.current?.click()}
              disabled={importBusy}
              className="mt-5 rounded-xl bg-sky-600 px-4 py-2 text-xs font-bold text-white hover:bg-sky-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-2"
            >
              {importBusy ? <Spinner /> : '📥'} Import File
            </button>
            <input
              ref={importInputRef}
              type="file"
              accept=".xlsx,.xls"
              onChange={handleImportFileChange}
              className="hidden"
            />

            <button
              onClick={() => handleSaveWorksheet(false)}
              disabled={saving || !hasUnsavedChanges}
              className="mt-5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-2"
            >
              {saving ? <Spinner /> : '💾'} Save Worksheet
            </button>

            <button
              onClick={resetWorksheet}
              disabled={!hasUnsavedChanges}
              className="mt-5 rounded-xl border border-rose-300 bg-rose-50 px-4 py-2 text-xs font-bold text-rose-700 hover:bg-rose-100 disabled:opacity-40 transition-all shadow-sm"
            >
              ↺ Reset Worksheet
            </button>

            <button
              onClick={handleGeneratePPTClick}
              disabled={loading}
              className="mt-5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-2"
            >
              📊 Generate PPT Report
            </button>

            <button
              onClick={handleExportExcel}
              disabled={loading}
              className="mt-5 rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-all"
            >
              📥 Export Excel
            </button>

            <button
              onClick={handleGenerateAnnualPPT}
              disabled={loading || !selectedPeriodId}
              className="mt-5 rounded-xl border border-indigo-500 bg-indigo-950 px-3 py-2 text-xs font-semibold text-indigo-200 hover:bg-indigo-900 disabled:opacity-40 transition-all"
              title="Merges every monthly report of this year into one annual analysis PPT"
            >
              🗓️ Annual PPT ({selectedPeriod ? selectedPeriod.period_start.slice(0, 4) : 'Year'})
            </button>
          </div>

          {selectedPeriod && (
            <div className="mt-4 rounded-xl border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-[11px] text-slate-300">
              Active range for <b className="text-white">PPT</b> & <b className="text-white">Excel export</b>:{' '}
              <span className="font-bold text-indigo-300">{selectedPeriod.report_type.toUpperCase()}</span>{' '}
              {selectedPeriod.period_start} → {selectedPeriod.period_end}
            </div>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="mt-6 flex gap-2 border-t border-slate-800 pt-4 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('worksheet')}
            className={`rounded-xl px-4 py-2 transition-all ${
              activeTab === 'worksheet'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            📋 Main Worksheet
          </button>

          <button
            onClick={() => setActiveTab('analysis')}
            className={`rounded-xl px-4 py-2 transition-all flex items-center gap-2 ${
              activeTab === 'analysis'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            🤖 AI Analysis
          </button>

          <button
            onClick={() => setActiveTab('verification')}
            className={`rounded-xl px-4 py-2 transition-all flex items-center gap-2 ${
              activeTab === 'verification'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            <span>✓ Verification Reference</span>
            {!verificationResults.isAllValid && (
              <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[10px] font-bold text-white">
                {verificationResults.totalFailed} ERROR{verificationResults.totalFailed > 1 ? 'S' : ''}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`rounded-xl px-4 py-2 transition-all ${
              activeTab === 'audit'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            📜 Audit History ({auditLogs.length})
          </button>

          <button
            onClick={() => setActiveTab('periods')}
            className={`rounded-xl px-4 py-2 transition-all ${
              activeTab === 'periods'
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-400 hover:bg-slate-800 hover:text-white'
            }`}
          >
            📅 Periods ({periods.length})
          </button>
        </div>
      </div>

      {error && <ErrorBox message={error} />}
      {successMsg && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-800 shadow-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg('')} className="text-emerald-600 hover:text-emerald-900">
            ✕
          </button>
        </div>
      )}

      {/* TAB 1: MAIN WORKSHEET GRID */}
      {activeTab === 'worksheet' && (
        <>
          {/* Calendar / Period Range Picker */}
          <Card className="border border-slate-300 shadow-lg">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-2xl bg-indigo-100 border border-indigo-200 flex items-center justify-center text-lg shrink-0">
                  📅
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Period Range Picker</h2>
                  <p className="text-[11px] text-slate-500 max-w-md">
                    Pick a week, month, year, or any date range. Apply it to load the matching reporting period into the
                    worksheet, PPT, and Excel export below.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-500 mb-1">Start date</label>
                  <input
                    type="date"
                    value={rangeStart}
                    onChange={(e) => setRangeStart(e.target.value)}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-500 mb-1">End date</label>
                  <input
                    type="date"
                    value={rangeEnd}
                    onChange={(e) => setRangeEnd(e.target.value)}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  {CALENDAR_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      onClick={() => {
                        const r = preset.range()
                        setRangeStart(r.start)
                        setRangeEnd(r.end)
                      }}
                      className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-100 hover:border-indigo-300 transition-all"
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={applyCalendarRange}
                    className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500 transition-all shadow-md"
                  >
                    Apply Range
                  </button>
                  <button
                    onClick={resetCalendar}
                    className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-all"
                  >
                    Reset
                  </button>
                </div>
              </div>
            </div>

            {calendarMatched ? (
              <div className="mt-4 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-2.5 text-xs font-semibold text-emerald-800">
                ✓ Loaded {calendarMatched.report_type.toUpperCase()} period · {calendarMatched.period_start} to{' '}
                {calendarMatched.period_end} · status: {calendarMatched.status}
              </div>
            ) : rangeStart || rangeEnd ? (
              <div className="mt-4 flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5 text-xs font-semibold text-amber-800">
                No period applied yet — press “Apply Range” to load the matching reporting period.
              </div>
            ) : null}
          </Card>

          <Card className="p-0 overflow-hidden border border-slate-300 shadow-lg">
          <div className="overflow-x-auto overflow-y-auto max-h-[75vh] pb-4 scrollbar-gutter-stable">
            <table className="w-full border-collapse text-xs">
              {/* Group Header (Row 1) */}
              <thead>
                <tr className="border-b border-slate-400">
                  <th className="sticky top-0 left-0 z-30 bg-slate-900 text-white px-4 py-3 text-left font-extrabold border-r-2 border-slate-700 min-w-[160px] shadow-md">
                    VERTICALS / NEW & FOLLOW-UP
                  </th>

                  {GROUPS.map((group) => (
                    <th
                      key={group.key}
                      colSpan={group.columns.length}
                      className={`sticky top-0 z-20 px-3 py-2 text-center font-black tracking-wide border-r-2 border-slate-400 ${group.headerBg}`}
                    >
                      {group.title}
                    </th>
                  ))}
                </tr>

                {/* Specific Column Names (Row 2) */}
                <tr className="border-b-2 border-slate-500 bg-slate-100 text-slate-800 font-bold">
                  <th className="sticky top-10 left-0 z-30 bg-slate-800 text-slate-200 px-4 py-2 text-left border-r-2 border-slate-700 text-[11px] shadow-sm">
                    Sub-team Row
                  </th>

                  {GROUPS.map((group) =>
                    group.columns.map((col) => (
                      <th
                        key={col.key}
                        className={`sticky top-10 z-20 px-2 py-2 text-center text-[10px] leading-tight border-r border-slate-300 min-w-[85px] max-w-[120px] whitespace-normal ${
                          col.isAuto ? 'bg-slate-200 font-extrabold text-slate-950' : group.headerBg
                        }`}
                      >
                        {col.label}
                      </th>
                    )),
                  )}
                </tr>
              </thead>

              <tbody>
                {/* NEW CASES SECTION */}
                {renderRowGroup('new', 'NEW CASES')}

                {/* FOLLOW-UP CASES SECTION */}
                {renderRowGroup('followup', 'FOLLOW-UP CASES')}

                {/* GRAND TOTAL ROW */}
                <tr className="bg-teal-200 font-black text-xs text-teal-950 border-t-4 border-b-4 border-teal-500">
                  <td className="sticky left-0 z-20 bg-teal-400 px-4 py-3 text-left border-r-2 border-teal-600 shadow-md whitespace-nowrap text-sm">
                    GRAND TOTAL
                  </td>
                  {GROUPS.map((group) =>
                    group.columns.map((col) => (
                      <td key={col.key} className="px-2 py-3 text-center border-r border-teal-300 text-xs font-black">
                        {calculatedSheet.grand_total?.[col.key] ?? 0}
                      </td>
                    )),
                  )}
                </tr>
              </tbody>
            </table>
          </div>
        </Card>

        {/* On-Screen Numpad */}
        {activeTab === 'worksheet' && selectedPeriodId && (
          <Card title="On-Screen Number Pad" subtitle="Click a cell first, then tap digits to build multi-digit numbers">
            <div className="flex flex-wrap items-start gap-4">
              <div className="grid grid-cols-3 gap-1.5 w-[200px]">
                {[1,2,3,4,5,6,7,8,9].map((d) => (
                  <button
                    key={d}
                    onClick={() => handleNumpadInput(String(d))}
                    className="h-10 rounded-lg bg-slate-100 border border-slate-300 text-sm font-bold text-slate-800 hover:bg-indigo-100 hover:border-indigo-400 active:bg-indigo-200 transition-all shadow-sm"
                  >
                    {d}
                  </button>
                ))}
                <button
                  onClick={() => handleNumpadInput('CLEAR')}
                  className="h-10 rounded-lg bg-rose-50 border border-rose-300 text-[11px] font-bold text-rose-700 hover:bg-rose-100 active:bg-rose-200 transition-all shadow-sm"
                >
                  Clear
                </button>
                <button
                  onClick={() => handleNumpadInput('0')}
                  className="h-10 rounded-lg bg-slate-100 border border-slate-300 text-sm font-bold text-slate-800 hover:bg-indigo-100 hover:border-indigo-400 active:bg-indigo-200 transition-all shadow-sm"
                >
                  0
                </button>
                <button
                  onClick={() => handleNumpadInput('BACKSPACE')}
                  className="h-10 rounded-lg bg-amber-50 border border-amber-300 text-[11px] font-bold text-amber-700 hover:bg-amber-100 active:bg-amber-200 transition-all shadow-sm"
                >
                  ⌫
                </button>
              </div>
              <div className="text-[11px] text-slate-500 leading-relaxed max-w-xs">
                <p className="font-semibold text-slate-700 mb-1">How it works:</p>
                <ul className="space-y-0.5 list-disc list-inside">
                  <li>Click any editable cell in the table to select it</li>
                  <li>Tap digit buttons to append — e.g. <strong>1→2→5</strong> = <strong>125</strong></li>
                  <li><strong>⌫</strong> removes the last digit</li>
                  <li><strong>Clear</strong> resets the cell to empty</li>
                  <li>You can also type directly with your keyboard</li>
                </ul>
              </div>
            </div>
          </Card>
        )}

        </>
      )}

      {/* TAB: AI ANALYSIS */}
      {activeTab === 'analysis' && (
        <CompareAnalysis />
      )}

      {/* TAB 2: VERIFICATION REFERENCE */}
      {activeTab === 'verification' && (
        <Card className="space-y-4">
          <div className="flex items-center justify-between border-b border-slate-200 pb-3">
            <div>
              <h2 className="text-base font-bold text-slate-900">Verification Reference Table</h2>
              <p className="text-xs text-slate-500">
                Formula check: Total Cases (derived from Gender) must match category totals across all rows.
              </p>
            </div>
            <div
              className={`rounded-xl px-4 py-1.5 text-xs font-bold ${
                verificationResults.isAllValid
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                  : 'bg-rose-100 text-rose-800 border border-rose-300'
              }`}
            >
              {verificationResults.isAllValid
                ? '✓ ALL FORMULAS VERIFIED (TRUE)'
                : `⚠ ${verificationResults.totalFailed} VERIFICATION ERROR(S)`}
            </div>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-slate-200">
            <table className="min-w-full text-left text-xs border-collapse">
              <thead className="bg-slate-900 text-white font-bold">
                <tr>
                  <th className="px-4 py-3 border-r border-slate-700">Verification Row</th>
                  <th className="px-4 py-3 border-r border-slate-700 text-center">Gender</th>
                  <th className="px-4 py-3 border-r border-slate-700 text-center">Mode of Session</th>
                  <th className="px-4 py-3 border-r border-slate-700 text-center">Referral Type</th>
                  <th className="px-4 py-3 border-r border-slate-700 text-center">Range of Concern</th>
                  <th className="px-4 py-3 text-center">Stakeholder</th>
                </tr>
              </thead>
              <tbody>
                {verificationResults.rows.map((row) => (
                  <tr
                    key={row.id}
                    className={`border-b border-slate-200 ${
                      row.isGrandTotal
                        ? 'bg-teal-50 font-bold'
                        : row.isTotal
                        ? 'bg-amber-50/60 font-semibold'
                        : 'hover:bg-slate-50'
                    }`}
                  >
                    <td className="px-4 py-3 font-semibold text-slate-900 border-r border-slate-200">
                      {row.label}
                      <span className="ml-2 font-mono text-[10px] text-slate-500">(Total: {row.totalCases})</span>
                    </td>

                    {['gender', 'session', 'referral', 'concern', 'stakeholder'].map((catKey) => {
                      const check = row.checks[catKey]
                      const isOk = check.passed

                      return (
                        <td key={catKey} className="px-4 py-2.5 text-center border-r border-slate-200">
                          <button
                            onClick={() => {
                              if (!isOk) {
                                setVerificationModal({
                                  rowLabel: row.label,
                                  categoryLabel: check.label,
                                  expected: check.expected,
                                  actual: check.actual,
                                  diff: check.actual - check.expected,
                                })
                              }
                            }}
                            className={`w-full rounded-xl px-3 py-1 font-extrabold text-xs transition-transform active:scale-95 ${
                              isOk
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : 'bg-rose-100 text-rose-800 border border-rose-300 hover:bg-rose-200 cursor-pointer shadow-sm animate-pulse'
                            }`}
                          >
                            {isOk ? 'TRUE' : 'FALSE'}
                          </button>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* TAB 3: AUDIT HISTORY */}
      {activeTab === 'audit' && (
        <Card className="space-y-4">
          <h2 className="text-base font-bold text-slate-900">Audit History & Mutation Log</h2>
          <p className="text-xs text-slate-500">Record of all cell modifications made to this reporting period.</p>

          <div className="overflow-x-auto rounded-2xl border border-slate-200">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-900 text-white font-bold">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                      No audit history logged for this period yet.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="border-b border-slate-200 hover:bg-slate-50">
                      <td className="px-4 py-3 text-slate-600 font-mono">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-900">{log.actor}</td>
                      <td className="px-4 py-3">
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-[10px] font-bold text-slate-700 border border-slate-300">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-700">
                        {JSON.stringify(log.details)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* TAB 4: PERIODS (CREATE / VIEW / EDIT / DELETE) */}
      {activeTab === 'periods' && (
        <Card className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">Manage Reporting Periods</h2>
              <p className="text-xs text-slate-500">
                Create, view, edit, and delete periods manually. The ID is generated automatically.
              </p>
            </div>
            {editingPeriodId && (
              <button
                onClick={resetPeriodForm}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-all"
              >
                ✕ Cancel edit
              </button>
            )}
          </div>

          {/* Create / Edit form */}
          <form onSubmit={savePeriod} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">Report Type</label>
                <select
                  value={periodForm.report_type}
                  onChange={(e) => setPeriodForm({ ...periodForm, report_type: e.target.value })}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                >
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">Period Start</label>
                <input
                  type="date"
                  required
                  value={periodForm.period_start}
                  onChange={(e) => setPeriodForm({ ...periodForm, period_start: e.target.value })}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">Period End</label>
                <input
                  type="date"
                  required
                  value={periodForm.period_end}
                  onChange={(e) => setPeriodForm({ ...periodForm, period_end: e.target.value })}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">Status</label>
                <select
                  value={periodForm.status}
                  onChange={(e) => setPeriodForm({ ...periodForm, status: e.target.value })}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                >
                  <option value="complete">Complete</option>
                  <option value="incomplete">Incomplete</option>
                  <option value="needs_review">Needs review</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">Source</label>
                <select
                  value={periodForm.source}
                  onChange={(e) => setPeriodForm({ ...periodForm, source: e.target.value })}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                >
                  <option value="manual">Manual</option>
                  <option value="upload">Upload</option>
                </select>
              </div>

              <div className="flex-1 min-w-[180px]">
                <label className="block text-[11px] font-semibold text-slate-500 mb-1">Title (optional)</label>
                <input
                  type="text"
                  value={periodForm.title}
                  onChange={(e) => setPeriodForm({ ...periodForm, title: e.target.value })}
                  placeholder="e.g. July Monthly Report"
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-600"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={periodSaving}
                  className="rounded-xl bg-indigo-600 px-5 py-2 text-xs font-bold text-white hover:bg-indigo-500 disabled:opacity-40 transition-all shadow-md flex items-center gap-2"
                >
                  {periodSaving ? <Spinner /> : editingPeriodId ? '💾 Update Period' : '＋ Create Period'}
                </button>
              </div>
            </div>
          </form>

          {/* Periods table */}
          <div className="overflow-x-auto rounded-2xl border border-slate-200">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-900 text-white font-bold">
                <tr>
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Period Range</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {periods.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                      No periods yet — create one above or import a file.
                    </td>
                  </tr>
                ) : (
                  periods.map((p) => (
                    <tr key={p.id} className="border-b border-slate-200 hover:bg-slate-50">
                      <td className="px-4 py-3 text-slate-400">#{p.id}</td>
                      <td className="px-4 py-3 capitalize font-semibold text-slate-900">{p.report_type}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {p.period_start} → {p.period_end}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={p.status} />
                      </td>
                      <td className="px-4 py-3 capitalize text-slate-600">{p.source}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1.5">
                          <button
                            onClick={() => startEditPeriod(p)}
                            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100 transition-all"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deletePeriod(p)}
                            className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-[11px] font-semibold text-rose-700 hover:bg-rose-100 transition-all"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* MODAL 1: VERIFICATION FAILURE DIAGNOSTIC MODAL */}
      {verificationModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border border-rose-200 animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-rose-100 pb-3">
              <div className="flex items-center gap-2 text-rose-700 font-bold text-base">
                <span>⚠</span> Verification Failed
              </div>
              <button
                onClick={() => setVerificationModal(null)}
                className="text-slate-400 hover:text-slate-700 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <div className="rounded-2xl bg-rose-50 p-4 border border-rose-200 space-y-2 text-rose-900">
                <div className="flex justify-between">
                  <span className="font-semibold text-slate-600">Row:</span>
                  <span className="font-bold">{verificationModal.rowLabel}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-semibold text-slate-600">Category:</span>
                  <span className="font-bold">{verificationModal.categoryLabel}</span>
                </div>
                <div className="flex justify-between border-t border-rose-200 pt-2">
                  <span className="font-semibold text-slate-600">Expected Total (Total Cases):</span>
                  <span className="font-bold font-mono">{verificationModal.expected}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-semibold text-slate-600">Calculated Category Total:</span>
                  <span className="font-bold font-mono">{verificationModal.actual}</span>
                </div>
                <div className="flex justify-between border-t border-rose-200 pt-2 text-sm font-bold text-rose-800">
                  <span>Difference / Missing:</span>
                  <span className="font-mono">{Math.abs(verificationModal.diff)}</span>
                </div>
              </div>

              <p className="text-slate-600 text-[11px]">
                To resolve, update cell entries in <b>{verificationModal.rowLabel}</b> under{' '}
                <b>{verificationModal.categoryLabel}</b> until the category sum equals Total Cases ({verificationModal.expected}).
              </p>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => {
                  setVerificationModal(null)
                  setActiveTab('worksheet')
                }}
                className="rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold text-white hover:bg-slate-800 transition-all shadow-md"
              >
                Return to Worksheet to Correct
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: GENERATE PPT WARNING MODAL */}
      {pptWarningModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border border-amber-200">
            <div className="flex items-center justify-between border-b border-amber-100 pb-3">
              <div className="flex items-center gap-2 text-amber-800 font-bold text-base">
                <span>⚠</span> Data Verification Warnings
              </div>
              <button
                onClick={() => setPptWarningModal(null)}
                className="text-slate-400 hover:text-slate-700 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs text-slate-700">
              <p className="font-medium text-slate-900">
                The worksheet contains <b>{pptWarningModal.failedCount} failed verification check(s)</b>.
              </p>
              <p>
                Generating PPT with unverified totals may display inconsistent counts across slides.
              </p>
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => {
                  setPptWarningModal(null)
                  setActiveTab('verification')
                }}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Return to Worksheet
              </button>
              <button
                onClick={executeGeneratePPT}
                className="rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white hover:bg-amber-500 shadow-md"
              >
                Continue and Generate
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: SAVE WITH VALIDATION WARNINGS */}
      {saveWarningModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl border border-amber-200">
            <div className="flex items-center justify-between border-b border-amber-100 pb-3">
              <div className="flex items-center gap-2 text-amber-800 font-bold text-base">
                <span>⚠</span> Verification Checks Failed
              </div>
              <button
                onClick={() => setSaveWarningModal(null)}
                className="text-slate-400 hover:text-slate-700 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs text-slate-700">
              <p className="font-medium text-slate-900">
                One or more rows failed verification — category sums (Gender, Mode, Referral,
                Concern, Stakeholder) don't match the row total.
              </p>
              <p>
                You can fix the values on the worksheet, or save anyway with warnings attached.
              </p>
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={() => {
                  setSaveWarningModal(null)
                  setError('')
                }}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Return to Fix Values
              </button>
              <button
                onClick={() => {
                  setSaveWarningModal(null)
                  handleSaveWorksheet(true)
                }}
                className="rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white hover:bg-amber-500 shadow-md"
              >
                Save Anyway (with warnings)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import File → Worksheet Preview Modal */}
      {importPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl border border-sky-200">
            <div className="flex items-center justify-between border-b border-sky-100 pb-3">
              <div className="flex items-center gap-2 text-sky-800 font-bold text-base">
                <span>📥</span> Import into Worksheet
              </div>
              <button
                onClick={closeImportModal}
                disabled={importBusy}
                className="text-slate-400 hover:text-slate-700 text-lg font-bold disabled:opacity-40"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs text-slate-700">
              <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 space-y-1">
                <p className="font-bold text-sm text-slate-900">
                  {importPreview.meta.report_type.toUpperCase()} —{' '}
                  {importPreview.meta.period_start} to {importPreview.meta.period_end}
                </p>
                <p>{importPreview.meta.title}</p>
                {importPreview.meta.title_range_mismatch && (
                  <p className="text-amber-700 font-semibold">
                    ⚠ Sheet title doesn't match the detected date range.
                  </p>
                )}
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-2.5 text-center">
                  <p className="text-lg font-extrabold text-emerald-700">{importPreview.counts.ready}</p>
                  <p className="font-semibold text-emerald-800">Ready</p>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-2.5 text-center">
                  <p className="text-lg font-extrabold text-amber-700">{importPreview.counts.warned}</p>
                  <p className="font-semibold text-amber-800">Warnings</p>
                </div>
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-center">
                  <p className="text-lg font-extrabold text-rose-700">{importPreview.counts.rejected}</p>
                  <p className="font-semibold text-rose-800">Rejected</p>
                </div>
              </div>

              {importPreview.duplicate && !importReplaceConfirm && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-3">
                  <p className="font-bold text-amber-900">⚠ Period already exists</p>
                  <p className="mt-1 text-amber-800">
                    A {importPreview.duplicate.label} report ({importPreview.duplicate.source}) already
                    exists. Importing will ask you to replace it.
                  </p>
                </div>
              )}

              {importReplaceConfirm && (
                <div className="rounded-xl border border-rose-300 bg-rose-50 p-3">
                  <p className="font-bold text-rose-900">Replace existing period?</p>
                  <p className="mt-1 text-rose-800">
                    "{importPreview.duplicate.label}" already exists. Replacing supersedes its current
                    data with this file's contents.
                  </p>
                </div>
              )}

              {importPreview.counts.rejected > 0 && (
                <p className="text-rose-700 font-medium">
                  {importPreview.counts.rejected} row(s) failed validation and will be imported as
                  incomplete — you can fix them on the worksheet afterwards.
                </p>
              )}
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              <button
                onClick={closeImportModal}
                disabled={importBusy}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
              >
                Cancel
              </button>
              {importReplaceConfirm ? (
                <button
                  onClick={() => confirmImportIntoWorksheet(true)}
                  disabled={importBusy}
                  className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-500 shadow-md flex items-center gap-2 disabled:opacity-40"
                >
                  {importBusy ? <Spinner /> : '↻'} Replace & Load
                </button>
              ) : (
                <button
                  onClick={() => confirmImportIntoWorksheet(false)}
                  disabled={importBusy}
                  className="rounded-xl bg-sky-600 px-4 py-2 text-xs font-bold text-white hover:bg-sky-500 shadow-md flex items-center gap-2 disabled:opacity-40"
                >
                  {importBusy ? <Spinner /> : '✓'} Import into Worksheet
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
