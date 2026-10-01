import { api } from './client'
import type { DriveBrowse, DriveStatus, ScanReport, SyncResult } from '../types/drive'

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : import.meta.env.BASE_URL.replace(/\/$/, '')

export const driveApi = {
  status: (projectId: number) => api.get<DriveStatus>(`/projects/${projectId}/drive/status`),
  scan: (projectId: number, ledgerPath?: string) =>
    api.post<ScanReport>(`/projects/${projectId}/drive/scan`, { ledger_path: ledgerPath || null }),
  sync: (projectId: number, ledgerPath?: string) =>
    api.post<SyncResult>(`/projects/${projectId}/drive/sync`, { ledger_path: ledgerPath || null }),
  browse: (projectId: number, path: string) =>
    api.get<DriveBrowse>(`/projects/${projectId}/drive/browse?path=${encodeURIComponent(path)}`),
  fileUrl: (projectId: number, path: string) =>
    `${API_BASE}/projects/${projectId}/drive/file?path=${encodeURIComponent(path)}`,
}
