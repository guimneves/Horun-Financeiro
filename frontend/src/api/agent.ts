import { api } from './client'

/** Uma instalação do Horun Agent (o programa no PC onde o OneDrive está
 * sincronizado — modo agente do drive). */
export interface AgentDevice {
  id: number
  device_name: string
  enrolled_at: string
  last_seen_at: string | null
  revoked_at: string | null
  /** versão que o agente informou na última consulta (antes da 0.3.0, nula) */
  agent_version: string | null
}

export interface EnrollCode {
  code: string
  expires_at: string | null
}

/** Rotas de admin do pacote do servidor do agente (app/agent_server); só o
 * admin do Core usa. As do próprio agente (/agent/enroll, /agent/tasks)
 * chegam pela porta estreita, não por aqui. */
export const agentApi = {
  listDevices: () => api.get<AgentDevice[]>('/agent/devices'),
  createEnrollCode: () => api.post<EnrollCode>('/agent/enroll-codes'),
  revokeDevice: (id: number) => api.post<unknown>(`/agent/devices/${id}/revoke`),
}
