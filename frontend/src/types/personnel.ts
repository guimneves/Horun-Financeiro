export interface Person {
  id: number
  project_id: number
  full_name: string
  cpf: string | null
}

export interface PersonnelAssignment {
  id: number
  project_id: number
  person_id: number
  person_name: string
  budget_position_id: number
  role_title: string
  // null quando o backend não revela valor pra este usuário (colaborador sem sessão de coordenador).
  monthly_rate: string | null
  start_date: string
  end_date: string | null
  status: 'ativo' | 'encerrado'
  accrued_months: string
  accrued_value: string | null
  committed_future_value: string | null
}
