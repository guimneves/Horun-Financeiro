import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { CategorySummary } from '../types'
import { CategorySummaryCard } from '../components/budget/CategorySummaryCard'
import type { ProjectContext } from './ProjectLayout'

export function DashboardPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [summary, setSummary] = useState<CategorySummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    budgetApi
      .summary(project.id)
      .then(setSummary)
      .catch((err) => setError(err.message))
  }, [project.id])

  if (project.active_revision_id === null) {
    return (
      <p className="p-6" style={{ color: 'var(--color-text-muted)' }}>
        Este projeto ainda não tem uma revisão orçamentária ativa — crie e ative uma revisão em
        "Orçamento" antes de lançar compras.
      </p>
    )
  }

  if (error) return <p className="p-6 text-red-600">Erro ao carregar resumo: {error}</p>
  if (summary === null) return <p className="p-6">Carregando…</p>

  const capital = summary.filter((s) => s.group === 'capital')
  const corrente = summary.filter((s) => s.group === 'corrente')

  return (
    <div className="p-6">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
        Despesas de Capital
      </h3>
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {capital.map((s) => (
          <CategorySummaryCard key={s.category} summary={s} />
        ))}
      </div>

      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
        Despesas Correntes
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {corrente.map((s) => (
          <CategorySummaryCard key={s.category} summary={s} />
        ))}
      </div>
    </div>
  )
}
