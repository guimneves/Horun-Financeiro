import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { projectsApi } from '../api/projects'
import type { Project } from '../types'

interface ProjectsContextValue {
  projects: Project[] | null
  error: string | null
  reload: () => void
}

const ProjectsContext = createContext<ProjectsContextValue | null>(null)

export function ProjectsProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(() => {
    // Traz também os arquivados: um projeto arquivado continua abrindo pelo
    // endereço (ProjectLayout); a lista e a barra lateral é que os escondem.
    projectsApi
      .list(true)
      .then((rows) => {
        setProjects(rows)
        setError(null)
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  return <ProjectsContext.Provider value={{ projects, error, reload }}>{children}</ProjectsContext.Provider>
}

/** Lista de projetos compartilhada entre a barra lateral e as páginas de
 * projeto — um só fetch, em vez de cada tela buscar por conta própria (a
 * mesma resposta já traz `my_role`, então também serve pra gate de nav). */
export function useProjects(): ProjectsContextValue {
  const ctx = useContext(ProjectsContext)
  if (!ctx) throw new Error('useProjects precisa estar dentro de <ProjectsProvider>')
  return ctx
}
