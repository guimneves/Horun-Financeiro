import { api } from './client'
import type { AuditEvent, Installment, Overview } from '../types'

export interface InstallmentInput {
  amount: string
  expected_date?: string | null
  note?: string
}

export const fundingApi = {
  overview: (projectId: number) => api.get<Overview>(`/projects/${projectId}/overview`),
  installments: (projectId: number) => api.get<Installment[]>(`/projects/${projectId}/installments`),
  replaceInstallments: (projectId: number, installments: InstallmentInput[]) =>
    api.put<Installment[]>(`/projects/${projectId}/installments`, { installments }),
  events: (projectId: number, entityType?: string, entityId?: number) => {
    const params = new URLSearchParams()
    if (entityType) params.set('entity_type', entityType)
    if (entityId !== undefined) params.set('entity_id', String(entityId))
    return api.get<AuditEvent[]>(`/projects/${projectId}/events?${params.toString()}`)
  },
}
