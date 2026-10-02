import { api } from './client'

/** Partes do previsto + rendimentos (frações de 0 a 1); valores em R$ só
 * para o coordenador — para o colaborador vêm nulos. */
export interface DashboardTotals {
  planned_value: string | null
  yield_amount: string | null
  committed: string | null
  executed: string | null
  balance: string | null
  executed_share: string | null
  committed_share: string | null
  balance_share: string | null
  overrun_share: string | null
}

export interface DashboardCategory extends DashboardTotals {
  category: string
  label: string
  group: 'capital' | 'corrente'
  items: number
}

export interface DashboardGroup extends DashboardTotals {
  group: 'capital' | 'corrente'
  label: string
}

export interface DashboardInstallment {
  number: number
  amount: string | null
  expected_date: string | null
  cumulative_amount: string | null
  utilization: string | null
}

export interface DashboardAlert {
  kind: 'saldo_negativo' | 'quase_no_fim' | 'compra_parada' | 'sem_valor'
  severity: 'danger' | 'warning' | 'info'
  message: string
  category: string | null
  item_number: number | null
  process_id: number | null
  amount: string | null
}

/** Um mês do ritmo de execução: acumulados até o fim do mês, em fração do
 * orçamento + rendimentos; realizado nulo nos meses futuros. */
export interface DashboardPacePoint {
  month: string
  personnel_share: string | null
  purchases_share: string | null
  expected_share: string | null
  received_share: string | null
  executed: string | null
  expected: string | null
  received: string | null
}

export interface DashboardPace {
  points: DashboardPacePoint[]
  estimated_share: string | null
  estimated_amount: string | null
  estimated_processes: number
}

export interface Dashboard {
  values_visible: boolean
  total: DashboardTotals
  groups: DashboardGroup[]
  categories: DashboardCategory[]
  installments: DashboardInstallment[]
  time_elapsed_share: string | null
  alerts: DashboardAlert[]
  pace: DashboardPace
}

export const dashboardApi = {
  get: (projectId: number) => api.get<Dashboard>(`/projects/${projectId}/dashboard`),
}
