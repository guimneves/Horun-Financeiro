const STORAGE_KEY = 'horun-financeiro-coordenador-token'

export function getCoordenadorToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setCoordenadorToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(STORAGE_KEY, token)
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // localStorage/sessionStorage indisponível (aba privada, política do navegador) — sem persistência, sem crash.
  }
}
