import { Link, useLocation } from 'react-router-dom'
import { useProjects } from '../../context/ProjectsContext'

const PROJECT_NAV_ITEMS = [
  { to: '', label: 'Resumo' },
  { to: 'budget', label: 'Orçamento' },
  { to: 'purchases', label: 'Compras' },
  { to: 'personnel', label: 'Equipe' },
]

const COORDENADOR_NAV_ITEMS = [
  { to: 'revisions', label: 'Revisões' },
  { to: 'members', label: 'Membros' },
]

export function AppSidebar() {
  const { projects, error } = useProjects()
  const location = useLocation()
  const match = location.pathname.match(/^\/projects\/(\d+)/)
  const currentProjectId = match ? Number(match[1]) : null

  return (
    <aside
      className="flex w-60 shrink-0 flex-col overflow-y-auto border-r p-3"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
    >
      <div className="mb-1 px-2 text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
        Projetos
      </div>

      {error && <p className="px-2 text-xs text-red-600">{error}</p>}
      {projects === null && !error && (
        <p className="px-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Carregando…
        </p>
      )}
      {projects?.length === 0 && (
        <p className="px-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Nenhum projeto ainda.
        </p>
      )}

      <nav className="flex flex-col gap-0.5">
        {projects?.map((project) => {
          const isCurrent = project.id === currentProjectId
          return (
            <div key={project.id}>
              <Link
                to={`/projects/${project.id}`}
                className="block truncate rounded-md px-2 py-1.5 text-sm"
                style={{
                  background: isCurrent ? 'var(--color-surface)' : 'transparent',
                  color: isCurrent ? 'var(--color-text)' : 'var(--color-text-muted)',
                  fontWeight: isCurrent ? 600 : 400,
                }}
                title={project.name}
              >
                {project.name}
              </Link>

              {isCurrent && (
                <div
                  className="ml-2 mt-0.5 mb-2 flex flex-col gap-0.5 border-l pl-2"
                  style={{ borderColor: 'var(--color-border)' }}
                >
                  {[...PROJECT_NAV_ITEMS, ...(project.my_role === 'coordenador' ? COORDENADOR_NAV_ITEMS : [])].map(
                    (item) => {
                      const to = `/projects/${project.id}${item.to ? `/${item.to}` : ''}`
                      const isActive = item.to === '' ? location.pathname === to : location.pathname.startsWith(to)
                      return (
                        <Link
                          key={item.to}
                          to={to}
                          className="rounded-md px-2 py-1 text-sm"
                          style={{
                            background: isActive ? 'var(--color-primary)' : 'transparent',
                            color: isActive ? 'var(--color-primary-contrast)' : 'var(--color-text-muted)',
                          }}
                        >
                          {item.label}
                        </Link>
                      )
                    },
                  )}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
