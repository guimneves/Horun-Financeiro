import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { BudgetItem, Category, Revision } from '../types'
import { BudgetItemsEditor } from '../components/budget/BudgetItemsEditor'
import { StatusBadge } from '../components/common/StatusBadge'
import type { ProjectContext } from './ProjectLayout'

export function BudgetRevisionEditorPage() {
  const { project } = useOutletContext<ProjectContext>()
  const { revisionId } = useParams()
  const navigate = useNavigate()
  const [revision, setRevision] = useState<Revision | null>(null)
  const [items, setItems] = useState<BudgetItem[] | null>(null)
  const [categories, setCategories] = useState<Category[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activating, setActivating] = useState(false)

  const load = useCallback(() => {
    if (!revisionId) return
    const rid = Number(revisionId)
    Promise.all([
      budgetApi.getRevision(project.id, rid),
      budgetApi.items(project.id, rid),
      budgetApi.categories(),
    ])
      .then(([rev, its, cats]) => {
        setRevision(rev)
        setItems(its)
        setCategories(cats)
      })
      .catch((err) => setError(err.message))
  }, [project.id, revisionId])

  useEffect(() => {
    load()
  }, [load])

  async function handleActivate() {
    if (!revision) return
    setActivating(true)
    try {
      await budgetApi.activateRevision(project.id, revision.id)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao ativar revisão.')
    } finally {
      setActivating(false)
    }
  }

  if (error) return <p className="p-6 text-red-600">Erro ao carregar revisão: {error}</p>
  if (revision === null || items === null || categories === null) return <p className="p-6">Carregando…</p>

  const isDraft = revision.status === 'rascunho'
  const isCoordenador = project.my_role === 'coordenador'
  const editable = isDraft && isCoordenador

  return (
    <div className="p-4 md:p-6">
      <button
        type="button"
        onClick={() => navigate(`/projects/${project.id}/revisions`)}
        className="mb-3 text-sm"
        style={{ color: 'var(--color-text-muted)' }}
      >
        ← Voltar para revisões
      </button>

      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
            {revision.label}
          </h2>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Vigência {revision.effective_date}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge
            label={revision.status === 'ativa' ? 'Ativa' : revision.status === 'rascunho' ? 'Rascunho' : 'Substituída'}
            tone={revision.status === 'ativa' ? 'success' : revision.status === 'rascunho' ? 'warning' : 'neutral'}
          />
          {isDraft && isCoordenador && (
            <button
              type="button"
              onClick={handleActivate}
              disabled={activating}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
            >
              {activating ? 'Ativando…' : 'Ativar revisão'}
            </button>
          )}
        </div>
      </div>

      {!editable && (
        <p className="mb-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {isDraft ? 'Só o coordenador pode editar.' : 'Esta revisão não é mais um rascunho — somente leitura.'}
        </p>
      )}

      <BudgetItemsEditor
        projectId={project.id}
        revisionId={revision.id}
        items={items}
        categories={categories}
        editable={editable}
        onChanged={load}
      />
    </div>
  )
}
