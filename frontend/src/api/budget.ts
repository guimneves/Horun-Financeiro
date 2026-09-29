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

export const budgetApi = {
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
