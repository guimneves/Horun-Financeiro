import { api, ApiError } from './client'
import type { PurchaseDocument } from '../types/purchase'
import type { Person, PersonnelAssignment } from '../types/personnel'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : import.meta.env.BASE_URL.replace(/\/$/, '')

export interface AssignmentCreateInput {
  person_id: number
  budget_position_id: number
  role_title: string
  monthly_rate: string
  start_date: string
}

export const personnelApi = {
  listPeople: (projectId: number) => api.get<Person[]>(`/projects/${projectId}/personnel`),
  createPerson: (projectId: number, fullName: string) =>
    api.post<Person>(`/projects/${projectId}/personnel`, { full_name: fullName }),

  listAssignments: (projectId: number) =>
    api.get<PersonnelAssignment[]>(`/projects/${projectId}/personnel-assignments`),
  createAssignment: (projectId: number, body: AssignmentCreateInput) =>
    api.post<PersonnelAssignment>(`/projects/${projectId}/personnel-assignments`, body),
  closeAssignment: (projectId: number, assignmentId: number, endDate: string) =>
    api.post<PersonnelAssignment>(`/projects/${projectId}/personnel-assignments/${assignmentId}/close`, {
      end_date: endDate,
    }),

  documents: (projectId: number, assignmentId: number) =>
    api.get<PurchaseDocument[]>(`/projects/${projectId}/personnel-assignments/${assignmentId}/documents`),
  downloadUrl: (projectId: number, assignmentId: number, docId: number) =>
    `${API_BASE}/projects/${projectId}/personnel-assignments/${assignmentId}/documents/${docId}/download`,

  async uploadReceipt(
    projectId: number,
    assignmentId: number,
    file: File,
    periodLabel?: string,
  ): Promise<PurchaseDocument> {
    const form = new FormData()
    if (periodLabel) form.append('period_label', periodLabel)
    form.append('file', file)
    const resp = await fetch(
      `${API_BASE}/projects/${projectId}/personnel-assignments/${assignmentId}/documents`,
      { method: 'POST', body: form },
    )
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new ApiError(resp.status, body.detail ?? resp.statusText)
    }
    return resp.json()
  },
}
