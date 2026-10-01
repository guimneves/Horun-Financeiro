import type { ItemBalance } from '../../types'
import { MoneyValue } from '../common/MoneyValue'

export function BudgetItemsTable({ items, categoryLabel }: { items: ItemBalance[]; categoryLabel: string }) {
  if (items.length === 0) return null

  return (
    <div className="mb-6">
      <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        {categoryLabel}
      </h3>
      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              <th className="px-3 py-2 text-left font-medium">Nº</th>
              <th className="px-3 py-2 text-left font-medium">Descrição</th>
              <th className="px-3 py-2 text-right font-medium" title="Quantidade prevista menos a já lançada em processos">
                Qtd. disponível
              </th>
              <th className="px-3 py-2 text-right font-medium">Planejado</th>
              <th className="px-3 py-2 text-right font-medium">Rendimentos</th>
              <th className="px-3 py-2 text-right font-medium">Comprometido</th>
              <th className="px-3 py-2 text-right font-medium">Realizado</th>
              <th className="px-3 py-2 text-right font-medium">Saldo</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.position_id} className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                  {item.item_number}
                </td>
                <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
                  {item.description}
                </td>
                <td
                  className="px-3 py-2 text-right"
                  style={{
                    color:
                      item.available_quantity !== null && Number(item.available_quantity) < 0
                        ? '#dc2626'
                        : 'var(--color-text-muted)',
                  }}
                >
                  {item.available_quantity === null ? '—' : `${Number(item.available_quantity)} / ${Number(item.planned_quantity)}`}
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
                  <MoneyValue value={item.balance} signColored />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
