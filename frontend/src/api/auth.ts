import { api } from './client'

export interface CoordenadorSession {
  token: string
  expires_at: number
}

export interface Me {
  user_id: string
  username: string
  role: string
  /** admin do Core — quem pode criar projeto */
  is_core_admin: boolean
}

export const authApi = {
  me: () => api.get<Me>('/auth/me'),
  login: (password: string) => api.post<CoordenadorSession>('/auth/coordenador-session', { password }),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<void>('/auth/coordenador-password', { current_password: currentPassword, new_password: newPassword }),
}
