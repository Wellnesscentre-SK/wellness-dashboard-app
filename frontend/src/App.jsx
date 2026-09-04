import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Import from './pages/Import'
import ManualEntry from './pages/ManualEntry'
import Periods from './pages/Periods'
import ImportHistory from './pages/ImportHistory'
import Insights from './pages/Insights'
import DataAnalysisAI from './pages/DataAnalysisAI'
import ReportsCenter from './pages/ReportsCenter'
import AISuggestions from './pages/AISuggestions'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center text-slate-500 text-sm">
        Loading…
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Dashboard />} />
            <Route path="/import" element={<Import />} />
            <Route path="/entry" element={<ManualEntry />} />
            <Route path="/reports/manual" element={<ManualEntry />} />
            <Route path="/reports/entry" element={<ManualEntry />} />
            <Route path="/manual" element={<ManualEntry />} />
            <Route path="/reports" element={<Navigate to="/reports/manual" replace />} />
            <Route path="/reports/center" element={<ReportsCenter />} />
            <Route path="/periods" element={<Periods />} />
            <Route path="/history" element={<ImportHistory />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/data-analysis" element={<DataAnalysisAI />} />
            <Route path="/ai-analysis" element={<DataAnalysisAI />} />
            <Route path="/ai-suggestions" element={<AISuggestions />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

