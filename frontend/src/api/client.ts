import { getCoordenadorToken } from '../lib/coordenadorSession'

// Em produção (plugado no Core), tudo roda na mesma origem sob o prefixo
// /m/<id>/ — a identidade chega ao backend via cabeçalho injetado pelo
// gateway, nunca pelo frontend (Prompt_Horun_Modulo.md, seção 6). Em
// desenvolvimento standalone, o frontend fala direto com o backend na
// porta 8000 (padrão do contrato de módulo).
export const API_BASE = import.meta.env.DEV
  ? 'http://localhost:8000'
  : import.meta.env.BASE_URL.replace(/\/$/, '')

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const coordenadorToken = getCoordenadorToken()
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(coordenadorToken ? { 'X-Horun-Coordenador-Token': coordenadorToken } : {}),
      ...init?.headers,
    },
  })

  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = body.detail ?? detail
    } catch {
      // corpo não era JSON — mantém o statusText
    }
    throw new ApiError(resp.status, detail)
  }

  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
