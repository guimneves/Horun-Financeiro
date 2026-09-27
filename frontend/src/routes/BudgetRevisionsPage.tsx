import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import type { Revision } from '../types'
import { StatusBadge } from '../components/common/StatusBadge'
import type { ProjectContext } from './ProjectLayout'

const STATUS_LABELS: Record<string, string> = {
  rascunho: 'Rascunho',
  ativa: 'Ativa',
  substituida: 'Substituída',
}

export function BudgetRevisionsPage() {
  const { project } = useOutletContext<ProjectContext>()
  const navigate = useNavigate()
  const [revisions, setRevisions] = useState<Revision[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [label, setLabel] = useState('')
  const [effectiveDate, setEffectiveDate] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(() => {
    budgetApi
      .revisions(project.id)
      .then((rows) => setRevisions([...rows].sort((a, b) => b.revision_number - a.revision_number)))
      .catch((err) => setError(err.message))
  }, [project.id])

  useEffect(() => {
    load()
  }, [load])

  async function handleCreate() {
    if (!label.trim() || !effectiveDate) return
    setSubmitting(true)
    try {
      const revision = await budgetApi.createRevision(project.id, { label: label.trim(), effective_date: effectiveDate })
      setShowNew(false)
      setLabel('')
      setEffectiveDate('')
      load()
      navigate(`/projects/${project.id}/revisions/${revision.id}/edit`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar revisão.')
    } finally {
      setSubmitting(false)
    }
  }

  if (error) return <p className="p-6 text-red-600">Erro ao carregar revisões: {error}</p>
  if (revisions === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Revisões orçamentárias
        </h2>
        <button
          type="button"
          onClick={() => setShowNew(true)}
          className="rounded-md px-4 py-2 text-sm font-medium"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          + Nova reformulação
        </button>
      </div>

      {showNew && (
        <div
          className="mb-4 flex flex-wrap items-end gap-2 rounded-lg border p-4"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
        >
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Rótulo
            </label>
            <input
              className="rounded-md border px-3 py-1.5 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              placeholder="Ex.: Reformulação Nº1"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Data de vigência
            </label>
            <input
              type="date"
              className="rounded-md border px-3 py-1.5 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              value={effectiveDate}
              onChange={(e) => setEffectiveDate(e.target.value)}
            />
          </div>
          <button
            type="button"
            onClick={handleCreate}
            disabled={submitting}
            className="rounded-md px-4 py-1.5 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            {submitting ? 'Criando…' : 'Criar rascunho'}
          </button>
          <button type="button" onClick={() => setShowNew(false)} style={{ color: 'var(--color-text-muted)' }}>
            Cancelar
          </button>
        </div>
      )}

      <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Uma reformulação nova clona os itens da revisão ativa como ponto de partida — o histórico das revisões
        anteriores fica intacto.
      </p>

      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              <th className="px-3 py-2 text-left font-medium">Nº</th>
              <th className="px-3 py-2 text-left font-medium">Rótulo</th>
              <th className="px-3 py-2 text-left font-medium">Status</th>
              <th className="px-3 py-2 text-left font-medium">Vigência</th>
              <th className="px-3 py-2 text-left font-medium">Criada por</th>
            </tr>
          </thead>
          <tbody>
            {revisions.map((revision) => (
              <tr key={revision.id} className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                  {revision.revision_number}
                </td>
                <td className="px-3 py-2">
                  <Link
                    to={`/projects/${project.id}/revisions/${revision.id}/edit`}
                    style={{ color: 'var(--color-primary)' }}
                  >
                    {revision.label}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  <StatusBadge
                    label={STATUS_LABELS[revision.status]}
                    tone={revision.status === 'ativa' ? 'success' : revision.status === 'rascunho' ? 'warning' : 'neutral'}
                  />
                </td>
                <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                  {revision.effective_date}
                </td>
                <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                  {revision.created_by_username}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
