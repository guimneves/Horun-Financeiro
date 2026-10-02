import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Category, ItemBalance } from '../../types'
import { MoneyValue } from '../common/MoneyValue'
import { AvailabilityBadge } from '../common/AvailabilityBadge'

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
        {item.available_quantity !== null ? (
          `${Number(item.available_quantity)} / ${Number(item.planned_quantity)}`
        ) : item.category === 'equipe_executora' ? (
          '—'
        ) : (
          <span title="Item de quantidade 1 gasto em várias compras: vale o saldo em R$">verba</span>
        )}
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
        {item.balance === null ? <AvailabilityBadge hasBalance={item.has_balance} /> : <MoneyValue value={item.balance} signColored />}
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
}: {
  categories: Category[]
  items: ItemBalance[]
  projectId: number
  initiallyOpen?: string[]
}) {
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

  if (groups.length === 0) return null
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
      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
        <table className="w-full text-sm" style={{ color: 'var(--color-text)' }}>
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
              const negatives = rows.filter((i) => (i.balance !== null ? Number(i.balance) < 0 : !i.has_balance)).length
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
    </div>
  )
}
