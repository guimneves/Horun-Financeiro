import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { useProjects } from '../context/ProjectsContext'
import type { Project } from '../types'

export interface ProjectContext {
  project: Project
  // recarrega a lista de projetos (ex. depois de mudar a pasta do drive em
  // Configurações) — o projeto vem do ProjectsContext
  reloadProject: () => void
}

export function ProjectLayout() {
  const { projectId } = useParams()
  const location = useLocation()
  const { projects, error, reload } = useProjects()

  if (error) return <p className="p-6 text-red-600">Erro ao carregar projeto: {error}</p>
  if (projects === null) return <p className="p-6">Carregando…</p>

  const project = projects.find((p) => p.id === Number(projectId))
  if (!project) return <p className="p-6 text-red-600">Projeto não encontrado ou sem acesso.</p>

  // Operador comum (colaborador) só enxerga Compras — Resumo, Orçamento,
  // Equipe, Revisões e Membros ficam ocultos mesmo se a URL for digitada
  // direto, não só desaparecidos da navegação.
  const isCoordenador = project.my_role === 'coordenador'
  const isPurchasesRoute = location.pathname.startsWith(`/projects/${project.id}/purchases`)
  if (!isCoordenador && !isPurchasesRoute) {
    return <Navigate to={`/projects/${project.id}/purchases`} replace />
  }

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
        <Outlet context={{ project, reloadProject: reload } satisfies ProjectContext} />
      </div>
    </div>
  )
}
