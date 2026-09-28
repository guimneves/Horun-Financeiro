import { Outlet, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext'
import type { Project } from '../types'

export interface ProjectContext {
  project: Project
}

export function ProjectLayout() {
  const { projectId } = useParams()
  const { projects, error } = useProjects()

  if (error) return <p className="p-6 text-red-600">Erro ao carregar projeto: {error}</p>
  if (projects === null) return <p className="p-6">Carregando…</p>

  const project = projects.find((p) => p.id === Number(projectId))
  if (!project) return <p className="p-6 text-red-600">Projeto não encontrado ou sem acesso.</p>

  return (
    <div className="flex flex-1 flex-col">
      <div className="border-b px-6 py-3" style={{ borderColor: 'var(--color-border)' }}>
        <div className="font-semibold" style={{ color: 'var(--color-text)' }}>
          {project.name}
        </div>
        <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Processo {project.code} · {project.my_role === 'coordenador' ? 'Coordenador' : 'Colaborador'}
        </div>
      </div>

      <div className="flex-1">
        <Outlet context={{ project } satisfies ProjectContext} />
      </div>
    </div>
  )
}
