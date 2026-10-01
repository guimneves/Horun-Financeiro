import { useState } from 'react'
import type { PurchaseProcess, TransitionAction } from '../../types/purchase'

interface ActionDef {
  action: TransitionAction
  label: string
  coordenadorOnly?: boolean
  needsReason?: boolean
  needsVendor?: boolean
  needsFinalValue?: boolean
  danger?: boolean
}

const ACTIONS_BY_STATUS: Record<string, ActionDef[]> = {
  verificacao_orcamento: [
    { action: 'avancar_cotacao', label: 'Avançar para cotação' },
    { action: 'cancelar', label: 'Cancelar processo', needsReason: true, danger: true },
  ],
  cotacao: [
    { action: 'solicitar_autorizacao', label: 'Solicitar autorização à COPPETEC' },
    { action: 'cancelar', label: 'Cancelar processo', needsReason: true, danger: true },
  ],
  aguardando_autorizacao: [
    { action: 'autorizar', label: 'Autorizar compra', coordenadorOnly: true, needsVendor: true },
    { action: 'rejeitar', label: 'Rejeitar', coordenadorOnly: true, needsReason: true, danger: true },
    { action: 'cancelar', label: 'Cancelar processo', needsReason: true, danger: true },
  ],
  autorizado: [
    { action: 'emitir_nota_fiscal', label: 'Registrar nota fiscal', needsFinalValue: true },
    { action: 'cancelar', label: 'Cancelar processo', needsReason: true, danger: true },
  ],
  nota_fiscal_emitida: [
    { action: 'confirmar_recebimento', label: 'Confirmar recebimento' },
    { action: 'cancelar', label: 'Cancelar processo', needsReason: true, danger: true },
  ],
  comprovante_recebimento: [{ action: 'concluir', label: 'Concluir processo' }],
}

// Ações que exigem um documento anexado — o coordenador pode dispensá-lo
// justificando (a justificativa fica no histórico do processo).
const GUARDED_ACTIONS = new Set<TransitionAction>([
  'avancar_cotacao',
  'solicitar_autorizacao',
  'autorizar',
  'emitir_nota_fiscal',
  'confirmar_recebimento',
])

interface ActionPanelProps {
  process: PurchaseProcess
  isCoordenador: boolean
  onTransition: (input: {
    action: TransitionAction
    reason?: string
    vendor?: string
    final_value?: string
    override_reason?: string
  }) => Promise<void>
}

export function ActionPanel({ process, isCoordenador, onTransition }: ActionPanelProps) {
  const [activeAction, setActiveAction] = useState<ActionDef | null>(null)
  const [reason, setReason] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [vendor, setVendor] = useState(process.vendor ?? '')
  const [finalValue, setFinalValue] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const available = (ACTIONS_BY_STATUS[process.status] ?? []).filter((a) => !a.coordenadorOnly || isCoordenador)

  if (available.length === 0) return null

  async function confirm(def: ActionDef) {
    setSubmitting(true)
    setError(null)
    try {
      await onTransition({
        action: def.action,
        reason: def.needsReason ? reason : undefined,
        vendor: def.needsVendor ? vendor : undefined,
        final_value: def.needsFinalValue ? finalValue : undefined,
        override_reason: isCoordenador && GUARDED_ACTIONS.has(def.action) && overrideReason.trim() ? overrideReason.trim() : undefined,
      })
      setActiveAction(null)
      setReason('')
      setOverrideReason('')
      setFinalValue('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao executar ação.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-lg border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
      <div className="mb-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        Ações
      </div>
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}

      {activeAction === null ? (
        <div className="flex flex-wrap gap-2">
          {available.map((def) => (
            <button
              key={def.action}
              type="button"
              onClick={() => setActiveAction(def)}
              className="rounded-md px-3 py-1.5 text-sm font-medium"
              style={{
                background: def.danger ? '#fee2e2' : 'var(--color-primary)',
                color: def.danger ? '#b91c1c' : 'var(--color-primary-contrast)',
              }}
            >
              {def.label}
            </button>
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          <div className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            {activeAction.label}
          </div>
          {activeAction.needsVendor && (
            <input
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              placeholder="Fornecedor vencedor"
              value={vendor}
              onChange={(e) => setVendor(e.target.value)}
            />
          )}
          {activeAction.needsFinalValue && (
            <input
              type="number"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              placeholder="Valor final da compra (R$)"
              value={finalValue}
              onChange={(e) => setFinalValue(e.target.value)}
            />
          )}
          {activeAction.needsReason && (
            <textarea
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              placeholder="Motivo"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
          {isCoordenador && GUARDED_ACTIONS.has(activeAction.action) && (
            <div>
              <input
                className="w-full rounded-md border px-3 py-2 text-sm"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                placeholder="Faltou o documento? Justifique para avançar mesmo assim (opcional)"
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
              />
              <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Só é usada se o documento exigido estiver faltando; fica registrada no histórico.
              </p>
            </div>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setActiveAction(null)}
              className="rounded-md px-3 py-1.5 text-sm"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Voltar
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={() => confirm(activeAction)}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
            >
              {submitting ? 'Enviando…' : 'Confirmar'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
