import { StatusBadge } from '../common/StatusBadge'
import { PURCHASE_STATUS_LABELS } from '../../types/purchase'

const TONE_BY_STATUS: Record<string, 'neutral' | 'success' | 'warning' | 'danger'> = {
  concluido: 'success',
  autorizado: 'success',
  aguardando_autorizacao: 'warning',
  nota_fiscal_emitida: 'warning',
  comprovante_recebimento: 'warning',
  rejeitado: 'danger',
  cancelado: 'danger',
}

export function PurchaseStatusBadge({ status }: { status: string }) {
  return <StatusBadge label={PURCHASE_STATUS_LABELS[status] ?? status} tone={TONE_BY_STATUS[status] ?? 'neutral'} />
}
