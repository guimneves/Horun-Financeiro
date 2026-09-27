import type { CategorySummary } from '../../types'
import { MoneyValue } from '../common/MoneyValue'

export function CategorySummaryCard({ summary }: { summary: CategorySummary }) {
  const hasValue = Number(summary.planned_value) !== 0
  return (
    <div
      className="rounded-lg border p-4"
      style={{
        borderColor: 'var(--color-border)',
        background: 'var(--color-bg-elevated)',
        opacity: hasValue ? 1 : 0.55,
      }}
    >
      <div className="mb-2 text-sm font-medium" style={{ color: 'var(--color-text)' }}>
        {summary.label}
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        <dt style={{ color: 'var(--color-text-muted)' }}>Planejado</dt>
        <dd className="text-right">
          <MoneyValue value={summary.planned_value} />
        </dd>
        <dt style={{ color: 'var(--color-text-muted)' }}>Comprometido</dt>
        <dd className="text-right">
          <MoneyValue value={summary.committed} />
        </dd>
        <dt style={{ color: 'var(--color-text-muted)' }}>Realizado</dt>
        <dd className="text-right">
          <MoneyValue value={summary.executed} />
        </dd>
        <dt className="font-medium" style={{ color: 'var(--color-text)' }}>
          Saldo
        </dt>
        <dd className="text-right">
          <MoneyValue value={summary.balance} signColored />
        </dd>
      </dl>
    </div>
  )
}
