import { api } from './client'
import type { Project } from '../types'

export const projectsApi = {
  list: () => api.get<Project[]>('/projects'),
  get: (projectId: number) => api.get<Project>(`/projects/${projectId}`),
}
