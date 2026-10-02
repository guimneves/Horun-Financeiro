import { API_BASE, api, ApiError } from './client'
import { getCoordenadorToken } from '../lib/coordenadorSession'
import type { PurchaseDocument } from '../types/purchase'
import type { Person, PersonnelAssignment } from '../types/personnel'

export interface AssignmentCreateInput {
  person_id: number
  budget_position_id: number
  role_title: string
  monthly_rate: string
  start_date: string
}

export interface PersonnelImportRow {
  item_number: number
  role_title: string
  person_name: string
  status: 'ativo' | 'encerrado'
  start_date: string
  end_date: string | null
  monthly_rate: string
  sheet_value: string | null
  accrued_value: string
  sheet_row: number
  position_found: boolean
  already_imported: boolean
}

export interface PersonnelImportPreview {
  rows: PersonnelImportRow[]
  warnings: string[]
  sheet_total: string
  accrued_total: string
}

export interface PersonnelImportResult {
  people_created: number
  assignments_created: number
  skipped: number
  warnings: string[]
}

function sheetForm(file: File): FormData {
  const form = new FormData()
  form.append('file', file)
  return form
}

export const personnelApi = {
  /** aba "Equipe Executora" da planilha — não grava nada */
  importPreview: (projectId: number, file: File) =>
    api.postForm<PersonnelImportPreview>(`/projects/${projectId}/personnel-import/preview`, sheetForm(file)),
  importPersonnel: (projectId: number, file: File) =>
    api.postForm<PersonnelImportResult>(`/projects/${projectId}/personnel-import`, sheetForm(file)),
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
    const token = getCoordenadorToken()
    const resp = await fetch(
      `${API_BASE}/projects/${projectId}/personnel-assignments/${assignmentId}/documents`,
      { method: 'POST', body: form, headers: token ? { 'X-Horun-Coordenador-Token': token } : undefined },
    )
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}))
      throw new ApiError(resp.status, body.detail ?? resp.statusText)
    }
    return resp.json()
  },
}
