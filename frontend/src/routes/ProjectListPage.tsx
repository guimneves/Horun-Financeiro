import { Link } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext'
import { StatusBadge } from '../components/common/StatusBadge'

export function ProjectListPage() {
  const { projects, error } = useProjects()

  if (error) return <p className="p-6 text-red-600">Erro ao carregar projetos: {error}</p>
  if (projects === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="p-6">
      <h2 className="mb-4 text-xl font-semibold" style={{ color: 'var(--color-text)' }}>
        Projetos
      </h2>

      {projects.length === 0 && (
        <p style={{ color: 'var(--color-text-muted)' }}>
          Você ainda não tem acesso a nenhum projeto.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="block rounded-lg border p-4 transition-colors hover:opacity-90"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Processo {project.code}
              </span>
              <StatusBadge label={project.my_role ?? ''} tone={project.my_role === 'coordenador' ? 'success' : 'neutral'} />
            </div>
            <div className="font-medium" style={{ color: 'var(--color-text)' }}>
              {project.name}
            </div>
            <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {project.funding_agency} · {project.foundation}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
