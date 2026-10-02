import { api } from './client'

export interface CoordenadorSession {
  token: string
  expires_at: number
}

export const authApi = {
  login: (password: string) => api.post<CoordenadorSession>('/auth/coordenador-session', { password }),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<void>('/auth/coordenador-password', { current_password: currentPassword, new_password: newPassword }),
}
