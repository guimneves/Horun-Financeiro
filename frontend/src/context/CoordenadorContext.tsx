import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { authApi, type Me } from '../api/auth'
import { getCoordenadorToken, setCoordenadorToken } from '../lib/coordenadorSession'

interface CoordenadorContextValue {
  /** true assim que existe um token salvo — a validade de verdade é sempre
   * conferida pelo backend a cada chamada; isso aqui só decide o que
   * mostrar na hora (botão "sair" vs. "entrar"). Só no desenvolvimento. */
  isElevated: boolean
  /** Quem é a pessoa (`/api/auth/me`); null enquanto carrega ou sem identidade. */
  me: Me | null
  /** Modo módulo: o papel vem do cargo no Horun e não há senha mestra. */
  rolesFromCore: boolean
  /** Pode abrir "Organização": coordenador(a) pelo cargo (modo módulo) ou
   * sessão elevada pela senha mestra (desenvolvimento). */
  canOrganize: boolean
  login: (password: string) => Promise<void>
  logout: () => void
}

const CoordenadorContext = createContext<CoordenadorContextValue | null>(null)

export function CoordenadorProvider({ children }: { children: ReactNode }) {
  const [isElevated, setIsElevated] = useState(() => getCoordenadorToken() !== null)
  const [me, setMe] = useState<Me | null>(null)

  useEffect(() => {
    authApi
      .me()
      .then((data) => {
        setMe(data)
        // Modo módulo: um token antigo da senha mestra não vale mais nada.
        if (data.roles_from_core) {
          setCoordenadorToken(null)
          setIsElevated(false)
        }
      })
      .catch(() => setMe(null))
  }, [])

  async function login(password: string) {
    const session = await authApi.login(password)
    setCoordenadorToken(session.token)
    setIsElevated(true)
  }

  function logout() {
    setCoordenadorToken(null)
    setIsElevated(false)
  }

  const rolesFromCore = me?.roles_from_core ?? false
  const canOrganize = rolesFromCore ? me?.module_role === 'coordenador' : isElevated

  return (
    <CoordenadorContext.Provider value={{ isElevated, me, rolesFromCore, canOrganize, login, logout }}>
      {children}
    </CoordenadorContext.Provider>
  )
}

export function useCoordenadorSession(): CoordenadorContextValue {
  const ctx = useContext(CoordenadorContext)
  if (!ctx) throw new Error('useCoordenadorSession precisa estar dentro de <CoordenadorProvider>')
  return ctx
}
