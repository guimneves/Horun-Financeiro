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
  my_role: 'coordenador' | 'colaborador' | null
}

export interface Category {
  code: string
  label: string
  group: 'capital' | 'corrente'
  is_personnel: boolean
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
