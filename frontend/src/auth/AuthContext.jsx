import { useEffect, useState, useCallback } from 'react'
import client, { setTokens, clearTokens } from '../api/client'
import { AuthContext } from './useAuth'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // An unauthenticated visitor does not need a round trip just to discover
    // that there is no session. This also prevents a sleeping backend from
    // holding the whole app on its initial loading screen.
    if (!localStorage.getItem('access')) {
      setLoading(false)
      return
    }

    client.get('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => {
        localStorage.removeItem('access')
        localStorage.removeItem('refresh')
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (username, password) => {
    const { data } = await client.post('/auth/login', { username, password })
    setTokens(data)
    const me = await client.get('/auth/me')
    setUser(me.data)
    return me.data
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
