import { StatusBadge } from './StatusBadge'

/** Usado no lugar do valor exato de saldo quando o backend não revelou o
 * número pra este usuário (colaborador sem sessão de coordenador). */
export function AvailabilityBadge({ hasBalance }: { hasBalance: boolean }) {
  return (
    <StatusBadge label={hasBalance ? 'Há saldo disponível' : 'Sem saldo disponível'} tone={hasBalance ? 'success' : 'danger'} />
  )
}
