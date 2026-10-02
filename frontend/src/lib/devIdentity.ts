// Seletor "Ver como" — só existe em build de desenvolvimento (import.meta.env.DEV).
// Permite alternar localmente entre usuários de teste (coordenador/colaborador)
// sem o Horun Core rodando, mandando os mesmos cabeçalhos que o Core injetaria
// em produção. Nunca usado fora de HORUN_DEV_MODE (o backend ignora esses
// cabeçalhos quando DEV_MODE=false).
const STORAGE_KEY = 'horun-financeiro-dev-identity'

export interface DevIdentity {
  userId: string
  username: string
}

export function getDevIdentity(): DevIdentity | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as DevIdentity) : null
  } catch {
    return null
  }
}

export function setDevIdentity(identity: DevIdentity | null): void {
  try {
    if (identity) localStorage.setItem(STORAGE_KEY, JSON.stringify(identity))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // localStorage indisponível — sem persistência, sem crash.
  }
}
