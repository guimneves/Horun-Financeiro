import { api } from './client'

export interface KnownUser {
  user_id: string
  username: string
}

export const knownUsersApi = {
  list: () => api.get<KnownUser[]>('/known-users'),
}
