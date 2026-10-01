import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { CategorySummary } from '../types'
import { CategorySummaryCard } from '../components/budget/CategorySummaryCard'
import { OverviewSection } from '../components/budget/OverviewSection'
import type { ProjectContext } from './ProjectLayout'

// Soma os valores de um grupo de categorias pro card agregado — se
// qualquer categoria vier com valor oculto (colaborador, ver
// core/redaction.py), o agregado também some (nunca mistura número real
// com zero de categoria redigida).
function aggregate(items: CategorySummary[], label: string): CategorySummary {
  const sum = (key: 'planned_value' | 'yield_amount' | 'committed' | 'executed' | 'balance') =>
    items.some((i) => i[key] === null) ? null : String(items.reduce((acc, i) => acc + Number(i[key]), 0))
  return {
    category: `__agg_${label}__`,
    label,
    group: 'capital',
    planned_value: sum('planned_value'),
    yield_amount: sum('yield_amount'),
    committed: sum('committed'),
    executed: sum('executed'),
    balance: sum('balance'),
    has_balance: items.some((i) => i.has_balance),
  }
}

export function DashboardPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [summary, setSummary] = useState<CategorySummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const isCoordenador = project.my_role === 'coordenador'

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

  if (!showDetails) {
    return (
      <div className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
            Resumo do projeto
          </h3>
          {isCoordenador && (
            <button
              type="button"
              onClick={() => setShowDetails(true)}
              className="text-sm font-medium"
              style={{ color: 'var(--color-primary)' }}
            >
              Ver detalhes por categoria →
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <CategorySummaryCard summary={aggregate(summary, 'Total geral')} />
          <CategorySummaryCard summary={aggregate(capital, 'Despesas de Capital')} />
          <CategorySummaryCard summary={aggregate(corrente, 'Despesas Correntes')} />
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <OverviewSection projectId={project.id} />

      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
          Despesas de Capital
        </h3>
        <button
          type="button"
          onClick={() => setShowDetails(false)}
          className="text-sm font-medium"
          style={{ color: 'var(--color-primary)' }}
        >
          ← Ver resumo
        </button>
      </div>
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
