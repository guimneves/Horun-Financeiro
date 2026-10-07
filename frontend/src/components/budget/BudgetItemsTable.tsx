import { Fragment, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { Category, ItemBalance, PurchaseCategory } from '../../types'
import { MoneyValue } from '../common/MoneyValue'
import { AvailabilityBadge } from '../common/AvailabilityBadge'
import { useIsMobile } from '../../lib/useIsMobile'

const muted = { color: 'var(--color-text-muted)' }
const MONEY_FIELDS = ['planned_value', 'yield_amount', 'committed', 'executed', 'balance'] as const
type MoneyField = (typeof MONEY_FIELDS)[number]

/** Soma em centavos (sem erro de ponto flutuante); nulo se algum valor está
 * oculto para este usuário (colaborador). */
function total(items: ItemBalance[], field: MoneyField): string | null {
  let cents = 0
  for (const item of items) {
    const value = item[field]
    if (value === null) return null
    cents += Math.round(Number(value) * 100)
  }
  return (cents / 100).toFixed(2)
}

function usedShare(items: ItemBalance[]): number | null {
  const available = Number(total(items, 'planned_value') ?? NaN) + Number(total(items, 'yield_amount') ?? NaN)
  const used = Number(total(items, 'committed') ?? NaN) + Number(total(items, 'executed') ?? NaN)
  return Number.isFinite(available) && Number.isFinite(used) && available > 0 ? used / available : null
}

function UsedBar({ share }: { share: number | null }) {
  if (share === null) return <span style={muted}>—</span>
  const over = share > 1
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full" style={{ background: 'var(--color-surface)' }}>
        <div className="h-full" style={{ width: `${Math.min(100, share * 100)}%`, background: over ? '#e34948' : '#2a78d6' }} />
      </div>
      <span className="w-10 text-right tabular-nums" style={over ? { color: '#dc2626', fontWeight: 600 } : muted}>
        {Math.round(share * 100)}%
      </span>
    </div>
  )
}

function QuantityText({ item }: { item: ItemBalance }) {
  if (item.available_quantity !== null) return <>{`${Number(item.available_quantity)} / ${Number(item.planned_quantity)}`}</>
  if (item.category === 'equipe_executora') return <>—</>
  return <span title="Item de quantidade 1 gasto em várias compras: vale o saldo em R$">verba</span>
}

function BalanceValue({ item }: { item: ItemBalance }) {
  return item.balance === null ? <AvailabilityBadge hasBalance={item.has_balance} /> : <MoneyValue value={item.balance} signColored />
}

/** Tipo de despesa liberado para compras novas: coordenador liga/desliga;
 * colaborador só vê o aviso quando está fechado. Equipe Executora não usa
 * o fluxo de compra — nada aparece. */
function PurchaseOpenControl({
  category,
  state,
  canManage,
  onToggle,
}: {
  category: Category
  state: PurchaseCategory | undefined
  canManage: boolean
  onToggle?: (category: Category, open: boolean) => Promise<void>
}) {
  const [saving, setSaving] = useState(false)
  if (category.is_personnel || state === undefined) return null
  if (!canManage || !onToggle) {
    return state.open ? null : (
      <span
        className="inline-block rounded-full px-2 py-0.5 text-xs font-normal"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
      >
        fechado para compras
      </span>
    )
  }
  async function change(open: boolean) {
    if (
      !open &&
      !window.confirm(
        `Fechar "${category.label}" para compras novas?

Ninguém poderá abrir compra neste tipo de despesa até ele ser liberado de novo. As compras já abertas continuam normalmente.`,
      )
    )
      return
    setSaving(true)
    try {
      await onToggle!(category, open)
    } finally {
      setSaving(false)
    }
  }
  return (
    <label
      className="inline-flex min-h-10 cursor-pointer items-center gap-2 text-xs font-normal md:min-h-0"
      style={{ color: state.open ? 'var(--color-text)' : 'var(--color-text-muted)' }}
      title={state.updated_by ? `Última mudança por ${state.updated_by}` : 'Liberado por padrão'}
      onClick={(e) => e.stopPropagation()}
    >
      <input
        type="checkbox"
        className="h-4 w-4"
        checked={state.open}
        disabled={saving}
        onChange={(e) => change(e.target.checked)}
      />
      {state.open ? 'Compra liberada' : 'Fechado para compras'}
    </label>
  )
}

/** Celular: uma linha da tabela = um cartão (Prompt_Horun_Modulo.md, seção 13). */
function ItemCard({ item, projectId }: { item: ItemBalance; projectId: number }) {
  const negativeQty = item.available_quantity !== null && Number(item.available_quantity) < 0
  const cells: [string, ReactNode][] = [
    ['Planejado', <MoneyValue value={item.planned_value} />],
    ['Rendimentos', <MoneyValue value={item.yield_amount} />],
    ['Comprometido', <MoneyValue value={item.committed} />],
    ['Realizado', <MoneyValue value={item.executed} />],
  ]
  return (
    <Link
      to={`/projects/${projectId}/budget/items/${item.position_id}`}
      className="block rounded-md border p-3"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 break-words text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          <span style={muted}>Nº {item.item_number} · </span>
          {item.description}
        </div>
        <div className="shrink-0 text-sm font-semibold tabular-nums">
          <BalanceValue item={item} />
        </div>
      </div>
      <dl className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs min-[360px]:grid-cols-2">
        {cells.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt style={muted}>{label}</dt>
            <dd className="tabular-nums" style={{ color: 'var(--color-text)' }}>
              {value}
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-2">
          <dt style={muted}>Qtd. disp.</dt>
          <dd style={{ color: negativeQty ? '#dc2626' : 'var(--color-text)' }}>
            <QuantityText item={item} />
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt style={muted}>Usado</dt>
          <dd>
            <UsedBar share={usedShare([item])} />
          </dd>
        </div>
      </dl>
    </Link>
  )
}

function ItemRow({ item, projectId }: { item: ItemBalance; projectId: number }) {
  return (
    <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
      <td className="py-2 pl-9 pr-3" style={muted}>
        {item.item_number}
      </td>
      <td className="px-3 py-2">
        <Link to={`/projects/${projectId}/budget/items/${item.position_id}`} style={{ color: 'var(--color-text)' }} className="hover:underline">
          {item.description}
        </Link>
      </td>
      <td
        className="px-3 py-2 text-right"
        style={{ color: item.available_quantity !== null && Number(item.available_quantity) < 0 ? '#dc2626' : 'var(--color-text-muted)' }}
      >
        <QuantityText item={item} />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={item.planned_value} />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={item.yield_amount} />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={item.committed} />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={item.executed} />
      </td>
      <td className="px-3 py-2 text-right">
        <BalanceValue item={item} />
      </td>
      <td className="px-3 py-2">
        <UsedBar share={usedShare([item])} />
      </td>
    </tr>
  )
}

/** Orçamento por categoria: primeiro só as categorias, com os totais; cada
 * uma se expande nos seus itens (pedido do usuário). */
export function BudgetItemsTable({
  categories,
  items,
  projectId,
  initiallyOpen = [],
  purchaseCategories,
  canManagePurchases = false,
  onTogglePurchase,
}: {
  categories: Category[]
  items: ItemBalance[]
  projectId: number
  initiallyOpen?: string[]
  /** tipos de despesa liberados para compra (ausente: não mostra nada) */
  purchaseCategories?: PurchaseCategory[]
  canManagePurchases?: boolean
  onTogglePurchase?: (category: Category, open: boolean) => Promise<void>
}) {
  const purchaseState = new Map((purchaseCategories ?? []).map((c) => [c.category, c]))
  const purchaseControl = (category: Category) => (
    <PurchaseOpenControl
      category={category}
      state={purchaseState.get(category.code)}
      canManage={canManagePurchases}
      onToggle={onTogglePurchase}
    />
  )
  const groups = categories
    .map((category) => ({ category, items: items.filter((i) => i.category === category.code) }))
    .filter((g) => g.items.length > 0)
  const [open, setOpen] = useState<Set<string>>(() => new Set(initiallyOpen))
  const toggle = (code: string) =>
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  const allOpen = groups.length > 0 && groups.every((g) => open.has(g.category.code))
  const isMobile = useIsMobile()

  if (groups.length === 0) return null
  const negativeCount = (rows: ItemBalance[]) =>
    rows.filter((i) => (i.balance !== null ? Number(i.balance) < 0 : !i.has_balance)).length
  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button
          type="button"
          className="text-sm"
          style={{ color: 'var(--color-primary)' }}
          onClick={() => setOpen(allOpen ? new Set() : new Set(groups.map((g) => g.category.code)))}
        >
          {allOpen ? 'Recolher todas' : 'Expandir todas'}
        </button>
      </div>
      {isMobile ? (
        <div className="space-y-2">
          {groups.map(({ category, items: rows }) => {
            const isOpen = open.has(category.code)
            const balance = total(rows, 'balance')
            const negatives = negativeCount(rows)
            return (
              <div
                key={category.code}
                className="rounded-lg border"
                style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
              >
                <button
                  type="button"
                  aria-expanded={isOpen}
                  onClick={() => toggle(category.code)}
                  className="flex w-full items-start gap-2 p-3 text-left"
                >
                  <span aria-hidden="true" className="w-4 shrink-0" style={muted}>
                    {isOpen ? '▾' : '▸'}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium" style={{ color: 'var(--color-text)' }}>
                      {category.label}
                    </span>
                    <span className="block text-xs" style={muted}>
                      {rows.length} {rows.length === 1 ? 'item' : 'itens'}
                      {negatives > 0 && <span style={{ color: '#dc2626' }}> · {negatives} com saldo negativo</span>}
                    </span>
                  </span>
                  <span className="shrink-0 text-right text-sm font-semibold tabular-nums">
                    <span className="block text-xs font-normal" style={muted}>
                      Saldo
                    </span>
                    {balance === null ? <AvailabilityBadge hasBalance={negatives === 0} /> : <MoneyValue value={balance} signColored />}
                    <span className="mt-1 block">
                      <UsedBar share={usedShare(rows)} />
                    </span>
                  </span>
                </button>
                {purchaseState.has(category.code) && !category.is_personnel && (canManagePurchases || !purchaseState.get(category.code)!.open) && (
                  <div className="px-3 pb-2 pl-9">{purchaseControl(category)}</div>
                )}
                {isOpen && (
                  <div className="space-y-2 border-t p-2" style={{ borderColor: 'var(--color-border)' }}>
                    {rows.map((item) => (
                      <ItemCard key={item.position_id} item={item} projectId={projectId} />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
        <table className="w-full min-w-[56rem] text-sm" style={{ color: 'var(--color-text)' }}>
          <thead>
            <tr style={{ background: 'var(--color-surface)', ...muted }}>
              <th className="px-3 py-2 text-left font-medium">Nº</th>
              <th className="px-3 py-2 text-left font-medium">Categoria / item</th>
              <th className="px-3 py-2 text-right font-medium" title="Quantidade prevista menos a já lançada em processos">
                Qtd. disponível
              </th>
              <th className="px-3 py-2 text-right font-medium">Planejado</th>
              <th className="px-3 py-2 text-right font-medium">Rendimentos</th>
              <th className="px-3 py-2 text-right font-medium">Comprometido</th>
              <th className="px-3 py-2 text-right font-medium">Realizado</th>
              <th className="px-3 py-2 text-right font-medium">Saldo</th>
              <th className="px-3 py-2 text-right font-medium">Usado</th>
            </tr>
          </thead>
          <tbody>
            {groups.map(({ category, items: rows }) => {
              const isOpen = open.has(category.code)
              const balance = total(rows, 'balance')
              const negatives = negativeCount(rows)
              return (
                <Fragment key={category.code}>
                  <tr
                    className="cursor-pointer border-t font-medium hover:opacity-90"
                    style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
                    onClick={() => toggle(category.code)}
                  >
                    <td className="px-3 py-2" style={muted}>
                      <span aria-hidden="true" className="inline-block w-4">
                        {isOpen ? '▾' : '▸'}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <button type="button" aria-expanded={isOpen} className="text-left font-medium" style={{ color: 'var(--color-text)' }}>
                        {category.label}
                      </button>
                      <span className="ml-2 text-xs font-normal" style={muted}>
                        {rows.length} {rows.length === 1 ? 'item' : 'itens'}
                        {negatives > 0 && <span style={{ color: '#dc2626' }}> · {negatives} com saldo negativo</span>}
                      </span>
                      <span className="ml-3 align-middle">{purchaseControl(category)}</span>
                    </td>
                    <td className="px-3 py-2" />
                    {MONEY_FIELDS.slice(0, 4).map((field) => (
                      <td key={field} className="px-3 py-2 text-right tabular-nums">
                        <MoneyValue value={total(rows, field)} />
                      </td>
                    ))}
                    <td className="px-3 py-2 text-right tabular-nums">
                      {balance === null ? <AvailabilityBadge hasBalance={negatives === 0} /> : <MoneyValue value={balance} signColored />}
                    </td>
                    <td className="px-3 py-2">
                      <UsedBar share={usedShare(rows)} />
                    </td>
                  </tr>
                  {isOpen && rows.map((item) => <ItemRow key={item.position_id} item={item} projectId={projectId} />)}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      )}
    </div>
  )
}
