import { getCoordenadorToken } from '../lib/coordenadorSession'
import { getDevIdentity } from '../lib/devIdentity'

// Em produção (plugado no Core), tudo roda na mesma origem sob o prefixo
// /m/<id>/ — a identidade chega ao backend via cabeçalho injetado pelo
// gateway, nunca pelo frontend (Prompt_Horun_Modulo.md, seção 6). Em
// desenvolvimento standalone, o frontend fala direto com o backend na
// porta 8000 (padrão do contrato de módulo). Toda rota da API fica sob
// /api — é o que o gateway do Core usa pra separar API de estáticos.
export const API_BASE =
  (import.meta.env.DEV
    ? (import.meta.env.VITE_API_URL ?? 'http://localhost:8000') // VITE_API_URL: outra porta, para testes
    : import.meta.env.BASE_URL.replace(/\/$/, '')) + '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const coordenadorToken = getCoordenadorToken()
  const devIdentity = import.meta.env.DEV ? getDevIdentity() : null
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      // FormData (envio de arquivo): o navegador põe o Content-Type com o boundary
      ...(typeof init?.body === 'string' ? { 'Content-Type': 'application/json' } : {}),
      ...(coordenadorToken ? { 'X-Horun-Coordenador-Token': coordenadorToken } : {}),
      ...(devIdentity
        ? { 'X-Horun-User-Id': devIdentity.userId, 'X-Horun-User': devIdentity.username, 'X-Horun-Role': 'admin' }
        : {}),
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
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: 'POST', body: form }),
}
