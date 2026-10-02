import type { PurchaseProcess } from '../../types/purchase'

/** Sinal de alerta: nota fiscal registrada acima do saldo do item, depois de
 * confirmada no aviso (ActionPanel). Não mostra valores — aparece para todos. */
export function OverBalanceAlert({ process, withLabel = false }: { process: PurchaseProcess; withLabel?: boolean }) {
  if (!process.over_balance_confirmed_at) return null
  const when = new Date(process.over_balance_confirmed_at).toLocaleDateString('pt-BR')
  const who = process.over_balance_confirmed_by ?? 'alguém'
  const text = `Nota fiscal acima do saldo do item — confirmada por ${who} em ${when}`
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium"
      style={{ background: '#fef3c7', color: '#92400e' }}
      title={text}
      aria-label={text}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 3 2 21h20L12 3Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <path d="M12 10v5M12 18h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
      {withLabel ? text : 'Acima do saldo'}
    </span>
  )
}
