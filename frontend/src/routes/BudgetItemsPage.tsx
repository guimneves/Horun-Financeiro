import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { BudgetItem, Category, ItemBalance, Revision } from '../types'
import { BudgetItemsTable } from '../components/budget/BudgetItemsTable'
import { BudgetItemsEditor } from '../components/budget/BudgetItemsEditor'
import type { ProjectContext } from './ProjectLayout'

export function BudgetItemsPage() {
  const { project } = useOutletContext<ProjectContext>()
  const isCoordenador = project.my_role === 'coordenador'
  // ?category=... (vindo do Resumo): só aquela categoria
  const [params] = useSearchParams()
  const onlyCategory = params.get('category')

  const [balance, setBalance] = useState<ItemBalance[] | null>(null)
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [revisions, setRevisions] = useState<Revision[] | null>(null)
  const [draftItems, setDraftItems] = useState<BudgetItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [activating, setActivating] = useState(false)

  const draftRevision = (revisions ?? []).find((r) => r.status === 'rascunho') ?? null

  const load = useCallback(() => {
    const requests: Promise<void>[] = [
      budgetApi.categories().then(setCategories),
      budgetApi.revisions(project.id).then(setRevisions),
    ]
    if (project.active_revision_id !== null) {
      requests.push(budgetApi.balance(project.id).then(setBalance))
    }
    Promise.all(requests).catch((err) => setError(err.message))
  }, [project.id, project.active_revision_id])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (draftRevision) {
      budgetApi.items(project.id, draftRevision.id).then(setDraftItems).catch((err) => setError(err.message))
    } else {
      setDraftItems(null)
    }
  }, [project.id, draftRevision?.id])

  async function handleCreateDraft() {
    setCreating(true)
    setError(null)
    try {
      const label = !revisions || revisions.length === 0 ? 'Baseline' : `Reformulação Nº${revisions.length}`
      await budgetApi.createRevision(project.id, {
        label,
        effective_date: new Date().toISOString().slice(0, 10),
      })
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar itens de orçamento.')
    } finally {
      setCreating(false)
    }
  }

  async function handleActivate() {
    if (!draftRevision) return
    setActivating(true)
    setError(null)
    try {
      await budgetApi.activateRevision(project.id, draftRevision.id)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao ativar orçamento.')
    } finally {
      setActivating(false)
    }
  }

  if (error) return <p className="p-6 text-red-600">Erro ao carregar orçamento: {error}</p>
  if (categories === null || revisions === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="p-6">
      {isCoordenador && draftRevision && draftItems !== null && (
        <div className="mb-6">
          <div
            className="mb-4 flex items-center justify-between rounded-lg border px-4 py-3"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
          >
            <p className="text-sm" style={{ color: 'var(--color-text)' }}>
              Editando rascunho <strong>{draftRevision.label}</strong> — estes itens ainda não valem para os saldos
              até serem ativados.
            </p>
            <button
              type="button"
              onClick={handleActivate}
              disabled={activating}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
            >
              {activating ? 'Ativando…' : 'Ativar orçamento'}
            </button>
          </div>
          <BudgetItemsEditor
            projectId={project.id}
            revisionId={draftRevision.id}
            items={draftItems}
            categories={categories}
            editable
            onChanged={() => budgetApi.items(project.id, draftRevision.id).then(setDraftItems)}
          />
        </div>
      )}

      {isCoordenador && !draftRevision && (
        <div className="mb-6">
          <button
            type="button"
            onClick={handleCreateDraft}
            disabled={creating}
            className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            {creating
              ? 'Criando…'
              : project.active_revision_id === null
                ? '+ Criar itens de orçamento'
                : '+ Editar itens (nova reformulação)'}
          </button>
        </div>
      )}

      {project.active_revision_id === null && !draftRevision && (
        <p style={{ color: 'var(--color-text-muted)' }}>
          Este projeto ainda não tem orçamento. {isCoordenador ? 'Clique acima para começar.' : ''}
        </p>
      )}

      {project.active_revision_id !== null && balance !== null && (
        <div>
          {draftRevision && (
            <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Saldo atual (revisão ativa) — os itens do rascunho acima ainda não entraram nesta conta.
            </p>
          )}
          {onlyCategory && (
            <p className="mb-3 text-sm">
              <Link to={`/projects/${project.id}/budget`} style={{ color: 'var(--color-primary)' }}>
                ← Ver todas as categorias
              </Link>
            </p>
          )}
          {categories.filter((c) => !onlyCategory || c.code === onlyCategory).map((category) => (
            <BudgetItemsTable
              key={category.code}
              categoryLabel={category.label}
              items={balance.filter((i) => i.category === category.code)}
              projectId={project.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
