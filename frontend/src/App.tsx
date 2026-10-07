import { useEffect, useState } from 'react'
import { ThemeProvider, ThemeToggle, HorunFooter } from '@horun/design-system'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import { ProjectListPage } from './routes/ProjectListPage'
import { ProjectLayout } from './routes/ProjectLayout'
import { DashboardPage } from './routes/DashboardPage'
import { BudgetItemsPage } from './routes/BudgetItemsPage'
import { BudgetItemDetailPage } from './routes/BudgetItemDetailPage'
import { PurchaseProcessesPage } from './routes/PurchaseProcessesPage'
import { PurchaseProcessDetailPage } from './routes/PurchaseProcessDetailPage'
import { PersonnelPage } from './routes/PersonnelPage'
import { BudgetRevisionsPage } from './routes/BudgetRevisionsPage'
import { BudgetRevisionEditorPage } from './routes/BudgetRevisionEditorPage'
import { ProjectMembersPage } from './routes/ProjectMembersPage'
import { DrivePage } from './routes/DrivePage'
import { OrganizationPage } from './routes/OrganizationPage'
import { ProjectSettingsPage } from './routes/ProjectSettingsPage'
import { ManualPage } from './routes/ManualPage'
import { CoordenadorProvider, useCoordenadorSession } from './context/CoordenadorContext'
import { ProjectsProvider, useProjects } from './context/ProjectsContext'
import { CoordenadorButton } from './components/common/CoordenadorButton'
import { DevUserSwitcher } from './components/common/DevUserSwitcher'
import { BackToHorunLink } from './components/common/BackToHorunLink'
import { AppSidebar } from './components/layout/AppSidebar'

/** Papel efetivo no modo módulo (vem do cargo no Horun), discreto no cabeçalho. */
function RoleBadge() {
  const { me, rolesFromCore } = useCoordenadorSession()
  if (!rolesFromCore || !me?.module_role) return null
  const label = me.module_role === 'coordenador' ? 'Coordenador(a)' : 'Colaborador(a)'
  return (
    <span
      className="max-w-[45vw] truncate rounded-full px-2.5 py-1 text-xs"
      style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
      title={`${me.username} — papel neste módulo, pelo seu cargo no Horun`}
    >
      <span className="hidden sm:inline">{me.username} · </span>
      {label}
    </span>
  )
}

function Header({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { isElevated, canOrganize, me } = useCoordenadorSession()
  const { reload } = useProjects()

  // `my_role` de cada projeto reflete a elevação assim que ela muda — sem
  // isto, o nav só mostraria Revisões/Membros depois da próxima navegação.
  useEffect(() => {
    reload()
  }, [isElevated, reload])

  return (
    <header
      className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2 md:px-4 md:py-3 print:hidden"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
    >
      <div className="flex min-w-0 items-center gap-2 md:gap-4">
        {/* celular: a barra lateral vira gaveta, aberta por este botão */}
        <button
          type="button"
          onClick={onOpenMenu}
          className="flex h-10 w-10 items-center justify-center rounded-md text-xl md:hidden"
          style={{ color: 'var(--color-text)' }}
          aria-label="Abrir menu"
        >
          ☰
        </button>
        <Link to="/" className="truncate text-lg font-semibold" style={{ color: 'var(--color-primary)' }}>
          Horun · Financeiro
        </Link>
        {canOrganize && (
          <Link to="/organizacao" className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Organização
          </Link>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {/* celular: o "Voltar ao Horun" fica na gaveta (AppSidebar) */}
        <BackToHorunLink className="hidden md:inline" />
        {import.meta.env.DEV && <DevUserSwitcher />}
        <RoleBadge />
        {/* senha mestra: só no desenvolvimento — no modo módulo o papel vem do cargo no Horun */}
        {me && !me.roles_from_core && <CoordenadorButton />}
        <ThemeToggle />
      </div>
    </header>
  )
}

function Shell() {
  // Gaveta do celular: fecha ao trocar de página (item escolhido), ao tocar
  // fora e com Esc. No computador a barra lateral fica sempre visível.
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname, location.search])
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  return (
          <div className="flex min-h-screen flex-col">
            <Header onOpenMenu={() => setMenuOpen(true)} />

            <div className="flex min-w-0 flex-1">
              <AppSidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

              <main className="min-w-0 flex-1 overflow-y-auto">
                <Routes>
                  <Route path="/" element={<ProjectListPage />} />
                  <Route path="/organizacao" element={<OrganizationPage />} />
                  <Route path="/projects/:projectId" element={<ProjectLayout />}>
                    <Route index element={<DashboardPage />} />
                    <Route path="budget" element={<BudgetItemsPage />} />
                    <Route path="budget/items/:positionId" element={<BudgetItemDetailPage />} />
                    <Route path="purchases" element={<PurchaseProcessesPage />} />
                    <Route path="purchases/:processId" element={<PurchaseProcessDetailPage />} />
                    <Route path="personnel" element={<PersonnelPage />} />
                    <Route path="revisions" element={<BudgetRevisionsPage />} />
                    <Route path="revisions/:revisionId/edit" element={<BudgetRevisionEditorPage />} />
                    <Route path="members" element={<ProjectMembersPage />} />
                    <Route path="drive" element={<DrivePage />} />
                    <Route path="settings" element={<ProjectSettingsPage />} />
                  </Route>
                  <Route path="/manual" element={<ManualPage />} />
                </Routes>
              </main>
            </div>

            <div className="print:hidden">
              <HorunFooter moduleName="Horun · Financeiro" />
            </div>
          </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <CoordenadorProvider>
        <ProjectsProvider>
          <Shell />
        </ProjectsProvider>
      </CoordenadorProvider>
    </ThemeProvider>
  )
}
