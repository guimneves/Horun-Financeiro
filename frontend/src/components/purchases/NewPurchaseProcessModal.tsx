import { useEffect, useMemo, useState } from 'react'
import { budgetApi } from '../../api/budget'
import { purchasesApi } from '../../api/purchases'
import type { ItemBalance, PurchaseCategory } from '../../types'
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
  const [purchaseCategories, setPurchaseCategories] = useState<PurchaseCategory[] | null>(null)
  // Passo 1: tipo de despesa (só os liberados pelos coordenadores); passo 2: item.
  const [category, setCategory] = useState<string | null>(null)
  const [itemQuery, setItemQuery] = useState('')
  const [positionId, setPositionId] = useState<number | null>(presetPositionId ?? null)
  const [title, setTitle] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unitValue, setUnitValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [checking, setChecking] = useState(false)
  const [availability, setAvailability] = useState<boolean | null>(null)

  useEffect(() => {
    Promise.all([budgetApi.balance(projectId), budgetApi.purchaseCategories(projectId)])
      .then(([balance, categories]) => {
        setItems(balance)
        setPurchaseCategories(categories)
        if (presetPositionId !== undefined) {
          setCategory(balance.find((i) => i.position_id === presetPositionId)?.category ?? null)
        }
      })
      .catch((err) => setError(err.message))
  }, [projectId, presetPositionId])

  // Tipos de despesa onde dá para abrir compra: liberados, fora da Equipe
  // Executora e com ao menos um item no orçamento ativo.
  const openCategories = useMemo(() => {
    const withItems = new Set((items ?? []).map((i) => i.category))
    return (purchaseCategories ?? []).filter((c) => c.open && !c.is_personnel && withItems.has(c.category))
  }, [items, purchaseCategories])
  const categoryState = purchaseCategories?.find((c) => c.category === category) ?? null
  const categoryClosed = categoryState !== null && !categoryState.open
  const categoryItems = useMemo(() => {
    const query = itemQuery.trim().toLowerCase()
    return (items ?? [])
      .filter((i) => i.category === category)
      .filter(
        (i) => !query || String(i.item_number) === query.replace(/^n[ºo°]?\s*/, '') || i.description.toLowerCase().includes(query),
      )
  }, [items, category, itemQuery])

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

        {items === null || purchaseCategories === null ? (
          <p className="mb-3 text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Carregando itens do orçamento…
          </p>
        ) : presetPositionId !== undefined ? (
          <div className="mb-3 text-sm" style={{ color: 'var(--color-text)' }}>
            <div style={{ color: 'var(--color-text-muted)' }}>{categoryState?.label ?? category}</div>
            {selected && (
              <div className="font-medium">
                Item {selected.item_number} — {selected.description}
              </div>
            )}
          </div>
        ) : openCategories.length === 0 ? (
          <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ background: '#fef9c3', color: '#a16207' }}>
            Nenhum tipo de despesa está liberado para compras neste projeto. Um coordenador precisa liberar em
            Orçamento (caixa "Compra liberada" no tipo de despesa).
          </p>
        ) : (
          <>
            <label
              htmlFor="new-purchase-category"
              className="mb-1 block text-sm font-medium"
              style={{ color: 'var(--color-text)' }}
            >
              1. Tipo de despesa
            </label>
            <select
              id="new-purchase-category"
              className="mb-3 w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              value={category ?? ''}
              onChange={(e) => {
                setCategory(e.target.value || null)
                setItemQuery('')
                updateAndResetCheck(setPositionId, null)
              }}
            >
              <option value="">Selecione o tipo de despesa…</option>
              {(['capital', 'corrente'] as const).map((group) => {
                const options = openCategories.filter((c) => c.group === group)
                if (options.length === 0) return null
                return (
                  <optgroup key={group} label={group === 'capital' ? 'Despesas de capital' : 'Despesas correntes'}>
                    {options.map((c) => (
                      <option key={c.category} value={c.category}>
                        {c.label} ({c.item_count} {c.item_count === 1 ? 'item' : 'itens'})
                      </option>
                    ))}
                  </optgroup>
                )
              })}
            </select>

            {category !== null && (
              <>
                <label
                  htmlFor="new-purchase-item-search"
                  className="mb-1 block text-sm font-medium"
                  style={{ color: 'var(--color-text)' }}
                >
                  2. Item
                </label>
                <input
                  id="new-purchase-item-search"
                  type="search"
                  className="mb-2 w-full rounded-md border px-3 py-2 text-sm"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                  value={itemQuery}
                  onChange={(e) => setItemQuery(e.target.value)}
                  placeholder="Buscar pelo nº ou pela descrição"
                />
                <div
                  role="listbox"
                  aria-label="Itens do tipo de despesa"
                  className="mb-3 max-h-56 overflow-y-auto rounded-md border"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  {categoryItems.length === 0 && (
                    <p className="px-3 py-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                      Nenhum item encontrado.
                    </p>
                  )}
                  {categoryItems.map((item) => {
                    const isSelected = item.position_id === positionId
                    return (
                      <button
                        key={item.position_id}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => updateAndResetCheck(setPositionId, item.position_id)}
                        className="flex w-full items-start justify-between gap-3 border-b px-3 py-2 text-left text-sm last:border-b-0"
                        style={{
                          borderColor: 'var(--color-border)',
                          background: isSelected ? 'var(--color-surface)' : 'transparent',
                          color: 'var(--color-text)',
                          fontWeight: isSelected ? 600 : 400,
                        }}
                      >
                        <span className="min-w-0 break-words">
                          <span style={{ color: 'var(--color-text-muted)' }}>Nº {item.item_number} — </span>
                          {item.description}
                        </span>
                        <span className="shrink-0 text-xs">
                          {item.balance === null ? (
                            <span style={{ color: item.has_balance ? 'var(--color-primary)' : '#dc2626' }}>
                              {item.has_balance ? 'há saldo' : 'sem saldo'}
                            </span>
                          ) : (
                            <MoneyValue value={item.balance} signColored />
                          )}
                        </span>
                      </button>
                    )
                  })}
                </div>
              </>
            )}
          </>
        )}

        {categoryClosed && (
          <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ background: '#fee2e2', color: '#b91c1c' }}>
            Este tipo de despesa não está liberado para compras — um coordenador pode liberá-lo em Orçamento.
          </p>
        )}

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
            disabled={
              submitting ||
              positionId === null ||
              categoryClosed ||
              !title.trim() ||
              !unitValue ||
              (exceedsBalance && blockOnExceed)
            }
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
