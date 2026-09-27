import { useEffect, useState } from 'react'
import { NavLink, Outlet, useParams } from 'react-router-dom'
import { projectsApi } from '../api/projects'
import type { Project } from '../types'

export interface ProjectContext {
  project: Project
}

// "Compras" e "Equipe" entram quando PurchaseProcess/Personnel existirem
// (Milestones 2/3 do plano) — sem isso aqui, os links ficariam mortos.
const NAV_ITEMS = [
  { to: '', label: 'Resumo', end: true },
  { to: 'budget', label: 'Orçamento' },
]

export function ProjectLayout() {
  const { projectId } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!projectId) return
    projectsApi
      .get(Number(projectId))
      .then(setProject)
      .catch((err) => setError(err.message))
  }, [projectId])

  if (error) return <p className="p-6 text-red-600">Erro ao carregar projeto: {error}</p>
  if (project === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="flex flex-1 flex-col">
      <div
        className="flex flex-wrap items-center gap-4 border-b px-6 py-3"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div>
          <div className="font-semibold" style={{ color: 'var(--color-text)' }}>
            {project.name}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Processo {project.code} · {project.my_role === 'coordenador' ? 'Coordenador' : 'Colaborador'}
          </div>
        </div>
        <nav className="flex gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${isActive ? '' : 'hover:opacity-80'}`
              }
              style={({ isActive }) => ({
                background: isActive ? 'var(--color-primary)' : 'transparent',
                color: isActive ? 'var(--color-primary-contrast)' : 'var(--color-text-muted)',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex-1">
        <Outlet context={{ project } satisfies ProjectContext} />
      </div>
    </div>
  )
}
