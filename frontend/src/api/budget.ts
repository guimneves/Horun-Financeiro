import { api } from './client'
import type { BudgetItem, Category, CategorySummary, ItemBalance, Revision } from '../types'

export interface RevisionCreateInput {
  label: string
  effective_date: string
  note?: string
}

export interface BudgetItemCreateInput {
  category: string
  item_number: number
  description: string
  justification?: string
  unit_value: string
  planned_quantity: string
  note?: string
  coppetec_process_number?: string
}

export interface BudgetItemUpdateInput {
  description?: string
  justification?: string
  unit_value?: string
  planned_quantity?: string
  note?: string
  coppetec_process_number?: string
}

export interface BudgetImportCategory {
  category: string
  label: string
  count: number
  planned_total: string
  yield_total: string
}

export interface BudgetImportPreview {
  categories: BudgetImportCategory[]
  items: { category: string; item_number: number; description: string; planned_value: string }[]
  skipped_sections: string[]
  warnings: string[]
}

export interface BudgetImportResult {
  revision: Revision
  items_created: number
  warnings: string[]
}

function sheetForm(file: File, fields: Record<string, string> = {}): FormData {
  const form = new FormData()
  for (const [key, value] of Object.entries(fields)) form.append(key, value)
  form.append('file', file)
  return form
}

export const budgetApi = {
  /** aba "Saldo por Item" da planilha de acompanhamento — não grava nada */
  importPreview: (projectId: number, file: File) =>
    api.postForm<BudgetImportPreview>(`/projects/${projectId}/budget-import/preview`, sheetForm(file)),
  /** cria uma revisão NOVA, em rascunho, com os itens da planilha */
  importBudget: (projectId: number, file: File, label: string, effectiveDate: string) =>
    api.postForm<BudgetImportResult>(
      `/projects/${projectId}/budget-import`,
      sheetForm(file, { label, effective_date: effectiveDate }),
    ),
  categories: () => api.get<Category[]>('/categories'),
  balance: (projectId: number) => api.get<ItemBalance[]>(`/projects/${projectId}/balance`),
  summary: (projectId: number) => api.get<CategorySummary[]>(`/projects/${projectId}/summary`),

  revisions: (projectId: number) => api.get<Revision[]>(`/projects/${projectId}/revisions`),
  getRevision: (projectId: number, revisionId: number) =>
    api.get<Revision>(`/projects/${projectId}/revisions/${revisionId}`),
  createRevision: (projectId: number, body: RevisionCreateInput) =>
    api.post<Revision>(`/projects/${projectId}/revisions`, body),
  activateRevision: (projectId: number, revisionId: number) =>
    api.post<Revision>(`/projects/${projectId}/revisions/${revisionId}/activate`),

  items: (projectId: number, revisionId: number) =>
    api.get<BudgetItem[]>(`/projects/${projectId}/revisions/${revisionId}/items`),
  createItem: (projectId: number, revisionId: number, body: BudgetItemCreateInput) =>
    api.post<BudgetItem>(`/projects/${projectId}/revisions/${revisionId}/items`, body),
  updateItem: (projectId: number, revisionId: number, itemId: number, body: BudgetItemUpdateInput) =>
    api.patch<BudgetItem>(`/projects/${projectId}/revisions/${revisionId}/items/${itemId}`, body),
  deleteItem: (projectId: number, revisionId: number, itemId: number) =>
    api.delete<void>(`/projects/${projectId}/revisions/${revisionId}/items/${itemId}`),
}
