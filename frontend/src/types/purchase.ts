export const PURCHASE_STATUS_LABELS: Record<string, string> = {
  verificacao_orcamento: 'Verificação de orçamento',
  cotacao: 'Cotação',
  aguardando_autorizacao: 'Aguardando autorização',
  autorizado: 'Autorizado',
  nota_fiscal_emitida: 'Nota fiscal emitida',
  comprovante_recebimento: 'Recebimento confirmado',
  concluido: 'Concluído',
  rejeitado: 'Rejeitado',
  cancelado: 'Cancelado',
}

export const PURCHASE_STATUS_ORDER = [
  'verificacao_orcamento',
  'cotacao',
  'aguardando_autorizacao',
  'autorizado',
  'nota_fiscal_emitida',
  'comprovante_recebimento',
  'concluido',
]

export const TERMINAL_STATUSES = new Set(['concluido', 'rejeitado', 'cancelado'])

export const DOC_TYPE_LABELS: Record<string, string> = {
  cotacao: 'Cotação',
  solicitacao_autorizacao: 'Solicitação enviada à COPPETEC',
  nota_fiscal: 'Nota fiscal / recibo',
  comprovante_recebimento: 'Comprovante de recebimento',
  recibo_pessoal: 'Recibo',
  outro: 'Outro',
}

export interface PurchaseProcess {
  id: number
  project_id: number
  budget_position_id: number
  process_number: string | null
  title: string
  vendor: string | null
  quantity: string
  estimated_unit_value: string
  estimated_value: string
  final_value: string | null
  asset_registration_flag: boolean
  status: string
  previous_attempt_id: number | null
  cancel_reason: string | null
  created_by_username: string
  created_at: string
  updated_at: string
  completed_at: string | null
  closed_at: string | null
}

export interface PurchaseDocument {
  id: number
  doc_type: string
  original_filename: string
  content_type: string
  size_bytes: number
  period_label: string | null
  note: string | null
  uploaded_by_username: string
  uploaded_at: string
}

export type TransitionAction =
  | 'avancar_cotacao'
  | 'solicitar_autorizacao'
  | 'autorizar'
  | 'rejeitar'
  | 'emitir_nota_fiscal'
  | 'confirmar_recebimento'
  | 'concluir'
  | 'cancelar'
