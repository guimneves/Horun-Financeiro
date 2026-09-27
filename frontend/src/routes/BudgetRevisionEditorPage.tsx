import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { BudgetItem, Category, Revision } from '../types'
import { EditableItemRow } from '../components/budget/EditableItemRow'
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
  const [newItem, setNewItem] = useState<{ category: string; itemNumber: string; description: string; unitValue: string; quantity: string } | null>(null)

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

  async function handleAddItem() {
    if (!newItem || !revision) return
    await budgetApi.createItem(project.id, revision.id, {
      category: newItem.category,
      item_number: Number(newItem.itemNumber),
      description: newItem.description,
      unit_value: newItem.unitValue,
      planned_quantity: newItem.quantity,
    })
    setNewItem(null)
    load()
  }

  if (error) return <p className="p-6 text-red-600">Erro ao carregar revisão: {error}</p>
  if (revision === null || items === null || categories === null) return <p className="p-6">Carregando…</p>

  const isDraft = revision.status === 'rascunho'
  const isCoordenador = project.my_role === 'coordenador'
  const editable = isDraft && isCoordenador

  return (
    <div className="p-6">
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

      {categories.map((category) => {
        const categoryItems = items.filter((i) => i.category === category.code)
        if (categoryItems.length === 0 && (!editable || newItem?.category !== category.code)) return null
        return (
          <div key={category.code} className="mb-6">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                {category.label}
              </h3>
              {editable && (
                <button
                  type="button"
                  onClick={() =>
                    setNewItem({ category: category.code, itemNumber: '', description: '', unitValue: '', quantity: '' })
                  }
                  className="text-xs"
                  style={{ color: 'var(--color-primary)' }}
                >
                  + item
                </button>
              )}
            </div>
            <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                    <th className="px-3 py-2 text-left font-medium">Nº</th>
                    <th className="px-3 py-2 text-left font-medium">Descrição</th>
                    <th className="px-3 py-2 text-right font-medium">V. Unit.</th>
                    <th className="px-3 py-2 text-right font-medium">Qtd.</th>
                    <th className="px-3 py-2 text-right font-medium">Valor</th>
                    {editable && <th className="px-3 py-2"></th>}
                  </tr>
                </thead>
                <tbody>
                  {categoryItems.map((item) => (
                    <EditableItemRow
                      key={item.id}
                      projectId={project.id}
                      revisionId={revision.id}
                      item={item}
                      editable={editable}
                      onChanged={load}
                    />
                  ))}
                  {editable && newItem?.category === category.code && (
                    <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                      <td className="px-2 py-1">
                        <input
                          type="number"
                          className="w-14 rounded border px-1 py-1"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          value={newItem.itemNumber}
                          onChange={(e) => setNewItem({ ...newItem, itemNumber: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          className="w-full rounded border px-2 py-1"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          placeholder="Descrição"
                          value={newItem.description}
                          onChange={(e) => setNewItem({ ...newItem, description: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          type="number"
                          className="w-24 rounded border px-2 py-1 text-right"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          value={newItem.unitValue}
                          onChange={(e) => setNewItem({ ...newItem, unitValue: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          type="number"
                          className="w-20 rounded border px-2 py-1 text-right"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          value={newItem.quantity}
                          onChange={(e) => setNewItem({ ...newItem, quantity: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1"></td>
                      <td className="px-2 py-1 text-right">
                        <button type="button" onClick={handleAddItem} style={{ color: 'var(--color-primary)' }}>
                          salvar
                        </button>{' '}
                        <button type="button" onClick={() => setNewItem(null)} style={{ color: 'var(--color-text-muted)' }}>
                          x
                        </button>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
    </div>
  )
}
