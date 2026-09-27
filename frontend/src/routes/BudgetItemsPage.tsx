import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { Category, ItemBalance } from '../types'
import { BudgetItemsTable } from '../components/budget/BudgetItemsTable'
import type { ProjectContext } from './ProjectLayout'

export function BudgetItemsPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [items, setItems] = useState<ItemBalance[] | null>(null)
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (project.active_revision_id === null) return
    Promise.all([budgetApi.balance(project.id), budgetApi.categories()])
      .then(([balance, cats]) => {
        setItems(balance)
        setCategories(cats)
      })
      .catch((err) => setError(err.message))
  }, [project.id, project.active_revision_id])

  if (project.active_revision_id === null) {
    return (
      <p className="p-6" style={{ color: 'var(--color-text-muted)' }}>
        Este projeto ainda não tem uma revisão orçamentária ativa.
      </p>
    )
  }

  if (error) return <p className="p-6 text-red-600">Erro ao carregar itens: {error}</p>
  if (items === null || categories === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="p-6">
      {categories.map((category) => (
        <BudgetItemsTable
          key={category.code}
          categoryLabel={category.label}
          items={items.filter((i) => i.category === category.code)}
        />
      ))}
    </div>
  )
}
