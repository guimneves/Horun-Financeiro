import { Link, useLocation } from 'react-router-dom'
import { useProjects } from '../../context/ProjectsContext'

const COORDENADOR_NAV_ITEMS = [
  { to: '', label: 'Resumo' },
  { to: 'budget', label: 'Orçamento' },
  { to: 'purchases', label: 'Compras' },
  { to: 'personnel', label: 'Equipe' },
  { to: 'revisions', label: 'Revisões' },
  { to: 'members', label: 'Membros' },
  { to: 'drive', label: 'Drive' },
  { to: 'settings', label: 'Configurações' },
]

// Operador comum (colaborador) só enxerga Compras — o resto fica oculto
// mesmo pra quem sabe a URL (ProjectLayout redireciona de qualquer jeito).
const OPERADOR_NAV_ITEMS = [{ to: 'purchases', label: 'Compras' }]

/** Barra lateral. No celular (abaixo de `md`) vira gaveta: fica escondida à
 * esquerda e abre por cima da página, com fundo escurecido (`open`); o App
 * fecha ao trocar de página e com Esc, o fundo fecha ao ser tocado. */
export function AppSidebar({ open = false, onClose }: { open?: boolean; onClose?: () => void }) {
  const { projects, error } = useProjects()
  const location = useLocation()
  const match = location.pathname.match(/^\/projects\/(\d+)/)
  const currentProjectId = match ? Number(match[1]) : null
  const manualActive = location.pathname.startsWith('/manual')

  return (
    <>
    {open && (
      <div className="fixed inset-0 z-40 bg-black/40 md:hidden print:hidden" onClick={onClose} aria-hidden="true" />
    )}
    <aside
      className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] shrink-0 flex-col overflow-y-auto border-r p-3 shadow-xl transition-transform md:static md:z-auto md:w-60 md:max-w-none md:translate-x-0 md:shadow-none print:hidden ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
      aria-label="Navegação"
    >
      <div className="mb-2 flex items-center justify-between md:hidden">
        <span className="px-2 font-semibold" style={{ color: 'var(--color-primary)' }}>
          Horun · Financeiro
        </span>
        <button
          type="button"
          onClick={onClose}
          className="flex h-10 w-10 items-center justify-center rounded-md text-lg"
          style={{ color: 'var(--color-text-muted)' }}
          aria-label="Fechar menu"
        >
          ✕
        </button>
      </div>
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
          const isCoordenador = project.my_role === 'coordenador'
          const navItems = isCoordenador ? COORDENADOR_NAV_ITEMS : OPERADOR_NAV_ITEMS
          return (
            <div key={project.id}>
              <Link
                to={`/projects/${project.id}${isCoordenador ? '' : '/purchases'}`}
                className="block truncate rounded-md px-2 py-2.5 text-sm md:py-1.5"
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
                  {navItems.map(
                    (item) => {
                      const to = `/projects/${project.id}${item.to ? `/${item.to}` : ''}`
                      const isActive = item.to === '' ? location.pathname === to : location.pathname.startsWith(to)
                      return (
                        <Link
                          key={item.to}
                          to={to}
                          className="rounded-md px-2 py-2.5 text-sm md:py-1"
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

      {/* Manual: sempre o último item, para todos (Prompt_Horun_Modulo.md, seção 12) */}
      <div className="mt-auto border-t pt-3" style={{ borderColor: 'var(--color-border)' }}>
        <Link
          to="/manual"
          className="block rounded-md px-2 py-2.5 text-sm md:py-1.5"
          style={{
            background: manualActive ? 'var(--color-primary)' : 'transparent',
            color: manualActive ? 'var(--color-primary-contrast)' : 'var(--color-text-muted)',
          }}
        >
          Manual
        </Link>
      </div>
    </aside>
    </>
  )
}
