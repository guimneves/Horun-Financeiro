import { useEffect, useState } from 'react'
import { budgetApi } from '../../api/budget'
import { purchasesApi } from '../../api/purchases'
import type { ItemBalance } from '../../types'
import { MoneyValue } from '../common/MoneyValue'
import { AvailabilityBadge } from '../common/AvailabilityBadge'

interface NewPurchaseProcessModalProps {
  projectId: number
  /** Política de saldo do projeto: true = recusa valor acima do saldo; false = só avisa */
  blockOnExceed: boolean
  onClose: () => void
  onCreated: () => void
  /** Quando informado, abre já travado neste item (ex.: modal acionado a partir da própria página do item). */
  presetPositionId?: number
}

export function NewPurchaseProcessModal({
  projectId,
  blockOnExceed,
  onClose,
  onCreated,
  presetPositionId,
}: NewPurchaseProcessModalProps) {
  const [items, setItems] = useState<ItemBalance[] | null>(null)
  const [positionId, setPositionId] = useState<number | null>(presetPositionId ?? null)
  const [title, setTitle] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unitValue, setUnitValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [checking, setChecking] = useState(false)
  const [availability, setAvailability] = useState<boolean | null>(null)

  useEffect(() => {
    budgetApi.balance(projectId).then(setItems).catch((err) => setError(err.message))
  }, [projectId])

  const selected = items?.find((i) => i.position_id === positionId) ?? null
  const estimatedValue = (Number(quantity) || 0) * (Number(unitValue) || 0)
  const exceedsBalance = selected !== null && selected.balance !== null && estimatedValue > Number(selected.balance)

  // Qualquer mudança no que está sendo checado invalida o resultado
  // anterior — nunca mostrar uma resposta de "disponível" desatualizada.
  function updateAndResetCheck<T>(setter: (value: T) => void, value: T) {
    setter(value)
    setAvailability(null)
  }

  async function handleCheckAvailability() {
    if (positionId === null || !unitValue) return
    setChecking(true)
    setError(null)
    try {
      const result = await purchasesApi.checkAvailability(projectId, {
        budget_position_id: positionId,
        quantity,
        estimated_unit_value: unitValue,
      })
      setAvailability(result.available)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao verificar disponibilidade.')
    } finally {
      setChecking(false)
    }
  }

  async function handleSubmit() {
    if (positionId === null || !title.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await purchasesApi.create(projectId, {
        budget_position_id: positionId,
        title: title.trim(),
        quantity,
        estimated_unit_value: unitValue,
      })
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar processo.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-2 sm:p-4">
      <div
        className="fin-modal-panel w-full max-w-md rounded-lg border p-4 sm:p-5"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
      >
        <h3 className="mb-4 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Novo processo de compra
        </h3>

        <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          Item de orçamento
        </label>
        <select
          className="mb-3 w-full rounded-md border px-3 py-2 text-sm disabled:opacity-70"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={positionId ?? ''}
          disabled={presetPositionId !== undefined}
          onChange={(e) => updateAndResetCheck(setPositionId, e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Selecione um item…</option>
          {items?.map((item) => (
            <option key={item.position_id} value={item.position_id}>
              {item.category} · Nº{item.item_number} — {item.description}
              {item.balance !== null ? ` (saldo ${item.balance})` : item.has_balance ? ' (há saldo)' : ' (sem saldo)'}
            </option>
          ))}
        </select>

        {selected && (
          <p className="mb-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Saldo disponível:{' '}
            {selected.balance === null ? (
              <AvailabilityBadge hasBalance={selected.has_balance} />
            ) : (
              <MoneyValue value={selected.balance} signColored />
            )}
          </p>
        )}

        <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          Título / descrição da compra
        </label>
        <input
          className="mb-3 w-full rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Ex.: Computador para acesso remoto"
        />

        <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              Quantidade
            </label>
            <input
              type="number"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              value={quantity}
              onChange={(e) => updateAndResetCheck(setQuantity, e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              Valor unitário estimado
            </label>
            <input
              type="number"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              value={unitValue}
              onChange={(e) => updateAndResetCheck(setUnitValue, e.target.value)}
            />
          </div>
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleCheckAvailability}
            disabled={checking || positionId === null || !unitValue}
            className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-surface)', color: 'var(--color-text)' }}
          >
            {checking ? 'Verificando…' : 'Verificar disponibilidade'}
          </button>
          {availability !== null &&
            (availability ? (
              <span className="text-sm" style={{ color: 'var(--color-primary)' }}>
                ✓ Há valor disponível para esta compra.
              </span>
            ) : (
              <span className="text-sm" style={{ color: '#b91c1c' }}>
                ✗ Não há valor disponível para esta compra.
              </span>
            ))}
        </div>

        {exceedsBalance && (
          blockOnExceed ? (
            <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ background: '#fee2e2', color: '#b91c1c' }}>
              Saldo insuficiente: o valor estimado (R$ {estimatedValue.toFixed(2)}) ultrapassa o saldo disponível deste
              item. Reduza o valor ou escolha outro item — não é possível criar o processo assim.
            </p>
          ) : (
            <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ background: '#fef9c3', color: '#a16207' }}>
              Aviso: o valor estimado (R$ {estimatedValue.toFixed(2)}) ultrapassa o saldo disponível deste item. Neste
              projeto isso é permitido — o processo será criado e o saldo ficará negativo.
            </p>
          )
        )}

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || positionId === null || !title.trim() || !unitValue || (exceedsBalance && blockOnExceed)}
            className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            {submitting ? 'Criando…' : 'Criar processo'}
          </button>
        </div>
      </div>
    </div>
  )
}
