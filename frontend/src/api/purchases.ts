import { API_BASE, api, ApiError } from './client'
import { getCoordenadorToken } from '../lib/coordenadorSession'
import { getDevIdentity } from '../lib/devIdentity'
import type { PurchaseDocument, PurchaseProcess, TransitionAction } from '../types/purchase'

export interface PurchaseProcessCreateInput {
  budget_position_id: number
  title: string
  quantity: string
  estimated_unit_value: string
  vendor?: string
  previous_attempt_id?: number
}

export interface TransitionInput {
  action: TransitionAction
  reason?: string
  vendor?: string
  process_number?: string
  final_value?: string
}

export interface AvailabilityCheckInput {
  budget_position_id: number
  quantity: string
  estimated_unit_value: string
}

export const purchasesApi = {
  list: (projectId: number, filters?: { positionId?: number }) => {
    const query = filters?.positionId !== undefined ? `?position_id=${filters.positionId}` : ''
    return api.get<PurchaseProcess[]>(`/projects/${projectId}/purchase-processes${query}`)
  },
  checkAvailability: (projectId: number, body: AvailabilityCheckInput) =>
    api.post<{ available: boolean }>(`/projects/${projectId}/purchase-processes/check-availability`, body),
  get: (projectId: number, processId: number) =>
    api.get<PurchaseProcess>(`/projects/${projectId}/purchase-processes/${processId}`),
  create: (projectId: number, body: PurchaseProcessCreateInput) =>
    api.post<PurchaseProcess>(`/projects/${projectId}/purchase-processes`, body),
  transition: (projectId: number, processId: number, body: TransitionInput) =>
    api.post<PurchaseProcess>(`/projects/${projectId}/purchase-processes/${processId}/transition`, body),
  documents: (projectId: number, processId: number) =>
    api.get<PurchaseDocument[]>(`/projects/${projectId}/purchase-processes/${processId}/documents`),
  deleteDocument: (projectId: number, processId: number, docId: number) =>
    api.delete<void>(`/projects/${projectId}/purchase-processes/${processId}/documents/${docId}`),
  downloadUrl: (projectId: number, processId: number, docId: number) =>
    `${API_BASE}/projects/${projectId}/purchase-processes/${processId}/documents/${docId}/download`,

  async uploadDocument(
    projectId: number,
    processId: number,
    docType: string,
    file: File,
    note?: string,
  ): Promise<PurchaseDocument> {
    const form = new FormData()
    form.append('doc_type', docType)
    if (note) form.append('note', note)
    form.append('file', file)

    const token = getCoordenadorToken()
    const devIdentity = import.meta.env.DEV ? getDevIdentity() : null
    const resp = await fetch(
      `${API_BASE}/projects/${projectId}/purchase-processes/${processId}/documents`,
      {
        method: 'POST',
        body: form,
        headers: {
          ...(token ? { 'X-Horun-Coordenador-Token': token } : {}),
          ...(devIdentity
            ? { 'X-Horun-User-Id': devIdentity.userId, 'X-Horun-User': devIdentity.username, 'X-Horun-Role': 'admin' }
            : {}),
        },
      },
    )
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new ApiError(resp.status, body.detail ?? resp.statusText)
    }
    return resp.json()
  },
}
