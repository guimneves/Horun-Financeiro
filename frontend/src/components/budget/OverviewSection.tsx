import { useEffect, useState } from 'react'
import { fundingApi } from '../../api/funding'
import type { Overview } from '../../types'
import { MoneyValue } from '../common/MoneyValue'

const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 1 })

const dateFormat = new Intl.DateTimeFormat('pt-BR', { month: '2-digit', year: 'numeric', timeZone: 'UTC' })

/** Equivalente ao "Quadro Resumo" da planilha: totais por grupo, total do
 *  projeto e % utilizado de cada parcela. */
export function OverviewSection({ projectId }: { projectId: number }) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fundingApi
      .overview(projectId)
      .then(setOverview)
      .catch((err) => setError(err.message))
  }, [projectId])

  if (error) return <p className="mb-6 text-sm text-red-600">Erro ao carregar o quadro resumo: {error}</p>
  if (overview === null) return null

  const rows = [...overview.groups, overview.total]

  return (
    <div className="mb-8">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
        Quadro resumo
      </h3>

      {overview.items_over_budget > 0 && (
        <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ background: '#fef9c3', color: '#a16207' }}>
          {overview.items_over_budget === 1
            ? '1 item está com saldo negativo.'
            : `${overview.items_over_budget} itens estão com saldo negativo.`}{' '}
          Veja em Orçamento.
        </p>
      )}

      <div className="mb-4 overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              <th className="px-3 py-2 text-left font-medium">Grupo</th>
              <th className="px-3 py-2 text-right font-medium">Planejado</th>
              <th className="px-3 py-2 text-right font-medium">Rendimentos</th>
              <th className="px-3 py-2 text-right font-medium">Comprometido</th>
              <th className="px-3 py-2 text-right font-medium">Realizado</th>
              <th className="px-3 py-2 text-right font-medium">Saldo</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.group}
                className="border-t"
                style={{ borderColor: 'var(--color-border)', fontWeight: row.group === 'total' ? 600 : 400 }}
              >
                <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
                  {row.label}
                </td>
                <td className="px-3 py-2 text-right">
                  <MoneyValue value={row.planned_value} />
                </td>
                <td className="px-3 py-2 text-right">
                  <MoneyValue value={row.yield_amount} />
                </td>
                <td className="px-3 py-2 text-right">
                  <MoneyValue value={row.committed} />
                </td>
                <td className="px-3 py-2 text-right">
                  <MoneyValue value={row.executed} />
                </td>
                <td className="px-3 py-2 text-right">
                  <MoneyValue value={row.balance} signColored />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {overview.installments.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {overview.installments.map((inst) => (
            <div
              key={inst.number}
              className="rounded-lg border p-3"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
            >
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {inst.number}ª parcela
                {inst.expected_date ? ` · ${dateFormat.format(new Date(inst.expected_date))}` : ''}
              </div>
              <div style={{ color: 'var(--color-text)' }}>
                <MoneyValue value={inst.amount} />
              </div>
              <div className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Utilizado:{' '}
                <strong style={{ color: 'var(--color-text)' }}>
                  {inst.utilization === null ? '—' : percent.format(Number(inst.utilization))}
                </strong>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
