import axios from 'axios'

const apiBaseUrl = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

const client = axios.create({ baseURL: apiBaseUrl })

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
  const { data, headers } = await client.post(
    `/reports/generate`,
    { period_id: periodId, format, ...(previousPeriodId && { previous_period_id: previousPeriodId }) },
    { responseType: 'blob' },
  )
  const disposition = headers['content-disposition'] || ''
  const match = disposition.match(/filename="?([^";]+)"?/)
  const filename = match ? match[1] : `report.${format === 'ppt' ? 'pptx' : format}`
  const url = URL.createObjectURL(new Blob([data]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default client
