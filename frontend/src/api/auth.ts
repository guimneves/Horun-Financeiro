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
  /** cargo no Horun: 1 admin máximo, 2 coordenador(a), 3 pesquisador, 4 técnico, 5 IC */
  level: number
  /** backend em HORUN_DEV_MODE (desenvolvimento local) */
  dev_mode: boolean
  /** modo módulo: papel pelo cargo no Horun, sem senha mestra */
  roles_from_core: boolean
  /** papel em todos os projetos no modo módulo (null no desenvolvimento) */
  module_role: 'coordenador' | 'colaborador' | null
}

export const authApi = {
  me: () => api.get<Me>('/auth/me'),
  login: (password: string) => api.post<CoordenadorSession>('/auth/coordenador-session', { password }),
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<void>('/auth/coordenador-password', { current_password: currentPassword, new_password: newPassword }),
}
