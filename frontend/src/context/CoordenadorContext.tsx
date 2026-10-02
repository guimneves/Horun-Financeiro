import { createContext, useContext, useState, type ReactNode } from 'react'
import { authApi } from '../api/auth'
import { getCoordenadorToken, setCoordenadorToken } from '../lib/coordenadorSession'

interface CoordenadorContextValue {
  /** true assim que existe um token salvo — a validade de verdade é sempre
   * conferida pelo backend a cada chamada; isso aqui só decide o que
   * mostrar na hora (botão "sair" vs. "entrar"). */
  isElevated: boolean
  login: (password: string) => Promise<void>
  logout: () => void
}

const CoordenadorContext = createContext<CoordenadorContextValue | null>(null)

export function CoordenadorProvider({ children }: { children: ReactNode }) {
  const [isElevated, setIsElevated] = useState(() => getCoordenadorToken() !== null)

  async function login(password: string) {
    const session = await authApi.login(password)
    setCoordenadorToken(session.token)
    setIsElevated(true)
  }

  function logout() {
    setCoordenadorToken(null)
    setIsElevated(false)
  }

  return (
    <CoordenadorContext.Provider value={{ isElevated, login, logout }}>{children}</CoordenadorContext.Provider>
  )
}

export function useCoordenadorSession(): CoordenadorContextValue {
  const ctx = useContext(CoordenadorContext)
  if (!ctx) throw new Error('useCoordenadorSession precisa estar dentro de <CoordenadorProvider>')
  return ctx
}
