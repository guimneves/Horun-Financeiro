import { useCallback, useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { personnelApi } from '../api/personnel'
import type { PersonnelAssignment } from '../types/personnel'
import { NewAssignmentModal } from '../components/personnel/NewAssignmentModal'
import { AssignmentRow } from '../components/personnel/AssignmentRow'
import type { ProjectContext } from './ProjectLayout'
import { PersonnelImportPanel } from '../components/personnel/PersonnelImportPanel'
import { useIsMobile } from '../lib/useIsMobile'

export function PersonnelPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [assignments, setAssignments] = useState<PersonnelAssignment[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const isMobile = useIsMobile()

  const load = useCallback(() => {
    personnelApi
      .listAssignments(project.id)
      .then(setAssignments)
      .catch((err) => setError(err.message))
  }, [project.id])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <p className="p-6 text-red-600">Erro ao carregar equipe: {error}</p>
  if (assignments === null) return <p className="p-6">Carregando…</p>

  const isCoordenador = project.my_role === 'coordenador'

  return (
    <div className="p-4 md:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Equipe Executora
        </h2>
        {isCoordenador && (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowImport(true)}
              className="rounded-md border px-4 py-2 text-sm font-medium"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
            >
              Importar da planilha
            </button>
            <button
              type="button"
              onClick={() => setShowNew(true)}
              className="rounded-md px-4 py-2 text-sm font-medium"
              style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
            >
              + Nova atribuição
            </button>
          </div>
        )}
      </div>

      {showImport && isCoordenador && (
        <PersonnelImportPanel projectId={project.id} onImported={load} onClose={() => setShowImport(false)} />
      )}

      {assignments.length === 0 ? (
        <p style={{ color: 'var(--color-text-muted)' }}>Nenhuma atribuição de pessoal cadastrada.</p>
      ) : isMobile ? (
        <div className="space-y-2">
          {assignments.map((assignment) => (
            <AssignmentRow
              key={assignment.id}
              projectId={project.id}
              assignment={assignment}
              isCoordenador={isCoordenador}
              onChanged={load}
              variant="card"
            />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                <th className="px-3 py-2 text-left font-medium">Membro</th>
                <th className="px-3 py-2 text-left font-medium">Cargo</th>
                <th className="px-3 py-2 text-left font-medium">Situação</th>
                <th className="px-3 py-2 text-left font-medium">Período</th>
                <th className="px-3 py-2 text-right font-medium">Valor mensal</th>
                <th className="px-3 py-2 text-right font-medium">Acumulado (realizado)</th>
                <th className="px-3 py-2 text-right font-medium">Comprometido futuro</th>
                <th className="px-3 py-2 text-right font-medium">Recibos</th>
                <th className="px-3 py-2 text-right font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment) => (
                <AssignmentRow
                  key={assignment.id}
                  projectId={project.id}
                  assignment={assignment}
                  isCoordenador={isCoordenador}
                  onChanged={load}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showNew && (
        <NewAssignmentModal
          projectId={project.id}
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false)
            load()
          }}
        />
      )}
    </div>
  )
}
