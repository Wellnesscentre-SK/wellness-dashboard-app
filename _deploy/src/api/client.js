import axios from 'axios'

// Vercel may provide either the API root or the Render origin. Normalize both
// forms so every request reaches Django's /api/ routes in production.
const configuredApiUrl = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')
const apiBaseUrl = configuredApiUrl === '/api' || configuredApiUrl.endsWith('/api')
  ? configuredApiUrl
  : `${configuredApiUrl}/api`

// Render free instances can take a moment to wake up, but a request must
// still fail visibly instead of leaving every page in an infinite spinner.
const client = axios.create({ baseURL: apiBaseUrl, timeout: 20000 })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshing = null

client.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    if (status === 401 && !original._retry && localStorage.getItem('refresh')) {
      original._retry = true
      refreshing =
        refreshing ||
        axios
          .post(`${apiBaseUrl}/auth/refresh`, { refresh: localStorage.getItem('refresh') })
          .then(({ data }) => {
            localStorage.setItem('access', data.access)
            return data.access
          })
          .finally(() => {
            refreshing = null
          })
      try {
        const token = await refreshing
        original.headers.Authorization = `Bearer ${token}`
        return client(original)
      } catch {
        localStorage.removeItem('access')
        localStorage.removeItem('refresh')
        window.location.href = '/login'
      }
    }
    if (status === 401) {
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export function setTokens({ access, refresh }) {
  localStorage.setItem('access', access)
  if (refresh) localStorage.setItem('refresh', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access')
  localStorage.removeItem('refresh')
}

export function apiError(error) {
  return (
    error?.response?.data?.message ||
    error?.response?.data?.detail ||
    error?.message ||
    'Something went wrong.'
  )
}

export async function generateReport(periodId, format, previousPeriodId) {
  const response = await client.post(
    `/reports/generate`,
    { period_id: periodId, format, ...(previousPeriodId && { previous_period_id: previousPeriodId }) },
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
      throw new Error(err.message || err.detail || 'Report generation failed.')
    } catch (e) {
      if (e instanceof Error) throw e
      throw new Error('Report generation failed.')
    }
  }

  const isExcel = String(format).toLowerCase() === 'xlsx'
  const PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  const mimeType = isExcel ? XLSX_MIME : PPTX_MIME
  const ext = isExcel ? '.xlsx' : '.pptx'

  let filename = `report_${periodId}${ext}`
  try {
    const disposition = response.headers?.['content-disposition'] || ''
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (match && match[1]) filename = match[1].replace(/["']/g, '').trim()
  } catch { /* header unreadable in some proxy environments */ }

  if (!/\.(pptx|xlsx|ppt|xls)$/i.test(filename)) {
    filename += ext
  }

  const url = URL.createObjectURL(new Blob([arrayBuf], { type: mimeType }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default client
