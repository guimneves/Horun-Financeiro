import { api } from './client'
import type { Project } from '../types'

export interface Membership {
  id: number
  project_id: number
  user_id: string
  username: string
  role: 'coordenador' | 'colaborador'
  created_at: string
}

export interface MembershipCreateInput {
  user_id: string
  username: string
  role: 'coordenador' | 'colaborador'
}

export interface ProjectUpdateInput {
  drive_folder?: string
  balance_policy?: 'bloquear' | 'avisar'
}

export const projectsApi = {
  list: () => api.get<Project[]>('/projects'),
  get: (projectId: number) => api.get<Project>(`/projects/${projectId}`),
  update: (projectId: number, body: ProjectUpdateInput) => api.patch<Project>(`/projects/${projectId}`, body),

  members: (projectId: number) => api.get<Membership[]>(`/projects/${projectId}/members`),
  addMember: (projectId: number, body: MembershipCreateInput) =>
    api.post<Membership>(`/projects/${projectId}/members`, body),
  removeMember: (projectId: number, membershipId: number) =>
    api.delete<void>(`/projects/${projectId}/members/${membershipId}`),
}
