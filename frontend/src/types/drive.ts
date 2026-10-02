export interface ProcessPlan {
  category: string
  item_number: number
  folder: string
  process_number: string
  title: string
  cancelled: boolean
  inferred_status: string
  /** criar | existe | sem_item_no_orcamento | duplicado_na_pasta */
  action: string
  value: string
  quantity: string
  vendor: string | null
  /** planilha | pendente | cancelado */
  value_source: string
  files_total: number
  new_files: number
  warnings: string[]
}

export interface ScanReport {
  summary: Record<string, number>
  processes: ProcessPlan[]
  unrecognized: { path: string; reason: string }[]
  ignored_folders: { path: string; reason: string }[]
  duplicate_numbers: string[]
  ledger_skipped: string[]
  ledger_unused: string[]
}

export interface SyncResult {
  processos_criados: number
  arquivos_vinculados: number
  summary: Record<string, number>
}

export interface DriveStatus {
  configured: boolean
  /** "local": o drive está no disco do servidor; "agent": lido pelo Horun
   * Agent no PC onde o OneDrive está sincronizado (cada ação espera o PC). */
  mode: 'local' | 'agent'
  project_folder: string | null
  available: boolean
  message: string | null
}

export interface DriveEntry {
  name: string
  is_dir: boolean
  rel_path: string
  size_bytes: number | null
}

export interface DriveBrowse {
  path: string
  parent: string | null
  entries: DriveEntry[]
}
