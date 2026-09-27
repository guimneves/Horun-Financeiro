import { api } from './client'
import type { Category, CategorySummary, ItemBalance, Revision } from '../types'

export const budgetApi = {
  categories: () => api.get<Category[]>('/categories'),
  revisions: (projectId: number) => api.get<Revision[]>(`/projects/${projectId}/revisions`),
  balance: (projectId: number) => api.get<ItemBalance[]>(`/projects/${projectId}/balance`),
  summary: (projectId: number) => api.get<CategorySummary[]>(`/projects/${projectId}/summary`),
}
