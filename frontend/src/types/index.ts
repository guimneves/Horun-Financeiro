export interface Project {
  id: number
  code: string
  name: string
  funding_agency: string
  foundation: string
  status: string
  start_date: string | null
  end_date: string | null
  active_revision_id: number | null
  drive_folder: string | null
  balance_policy: 'bloquear' | 'avisar'
  /** arquivado: fora da lista e da sincronização automática; os dados ficam */
  archived_at: string | null
  archived_by: string | null
  my_role: 'coordenador' | 'colaborador' | null
}

export interface Category {
  code: string
  label: string
  group: 'capital' | 'corrente'
  is_personnel: boolean
}

/** Tipo de despesa e se está liberado para compras novas neste projeto */
export interface PurchaseCategory {
  category: string
  label: string
  group: 'capital' | 'corrente'
  is_personnel: boolean
  /** liberado pelos coordenadores (Equipe Executora: sempre false) */
  open: boolean
  /** itens da revisão ativa neste tipo de despesa */
  item_count: number
  updated_by: string | null
  updated_at: string | null
}

export interface Revision {
  id: number
  project_id: number
  revision_number: number
  label: string
  status: 'rascunho' | 'ativa' | 'substituida'
  effective_date: string
  note: string
  created_by_username: string
}

export interface BudgetItem {
  id: number
  revision_id: number
  position_id: number
  category: string
  item_number: number
  description: string
  justification: string
  // null quando o backend não revela valor pra este usuário (colaborador sem sessão de coordenador).
  unit_value: string | null
  planned_quantity: string
  planned_value: string | null
  yield_amount: string | null
  note: string
  coppetec_process_number: string | null
}

export interface ItemBalance {
  position_id: number
  category: string
  item_number: number
  description: string
  justification: string
  unit_value: string | null
  planned_quantity: string
  planned_value: string | null
  yield_amount: string | null
  committed: string | null
  executed: string | null
  balance: string | null
  has_balance: boolean
  coppetec_process_number: string | null
  /** "Quant. Disponível" da planilha; nulo na Equipe Executora */
  available_quantity: string | null
}

export interface CategorySummary {
  category: string
  label: string
  group: 'capital' | 'corrente'
  planned_value: string | null
  yield_amount: string | null
  committed: string | null
  executed: string | null
  balance: string | null
  has_balance: boolean
}

export interface Installment {
  number: number
  amount: string
  expected_date: string | null
  note: string
  cumulative_amount: string
  /** Fração de 0 a 1; nula enquanto a parcela anterior não foi toda utilizada (o "-" da planilha) */
  utilization: string | null
}

export interface GroupTotal {
  group: string
  label: string
  planned_value: string
  yield_amount: string
  committed: string
  executed: string
  balance: string
}

/** Equivalente ao "Quadro Resumo" da planilha */
export interface Overview {
  groups: GroupTotal[]
  total: GroupTotal
  total_executed: string
  installments: Installment[]
  items_over_budget: number
}

export interface AuditEvent {
  id: number
  entity_type: string
  entity_id: number | null
  action: string
  detail: string
  username: string
  created_at: string
}
