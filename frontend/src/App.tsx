import { ThemeProvider, ThemeToggle, HorunFooter } from '@horun/design-system'
import { Link, Route, Routes } from 'react-router-dom'
import { ProjectListPage } from './routes/ProjectListPage'
import { ProjectLayout } from './routes/ProjectLayout'
import { DashboardPage } from './routes/DashboardPage'
import { BudgetItemsPage } from './routes/BudgetItemsPage'
import { PurchaseProcessesPage } from './routes/PurchaseProcessesPage'
import { PurchaseProcessDetailPage } from './routes/PurchaseProcessDetailPage'
import { PersonnelPage } from './routes/PersonnelPage'
import { BudgetRevisionsPage } from './routes/BudgetRevisionsPage'
import { BudgetRevisionEditorPage } from './routes/BudgetRevisionEditorPage'
import { ProjectMembersPage } from './routes/ProjectMembersPage'
import { OrganizationPage } from './routes/OrganizationPage'
import { CoordenadorProvider, useCoordenadorSession } from './context/CoordenadorContext'
import { CoordenadorButton } from './components/common/CoordenadorButton'

function Header() {
  const { isElevated } = useCoordenadorSession()
  return (
    <header
      className="flex items-center justify-between border-b px-4 py-3"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
    >
      <div className="flex items-center gap-4">
        <Link to="/" className="text-lg font-semibold" style={{ color: 'var(--color-primary)' }}>
          Horun · Financeiro
        </Link>
        {isElevated && (
          <Link to="/organizacao" className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Organização
          </Link>
        )}
      </div>
      <div className="flex items-center gap-2">
        <CoordenadorButton />
        <ThemeToggle />
      </div>
    </header>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <CoordenadorProvider>
        <div className="flex min-h-screen flex-col">
          <Header />

          <Routes>
            <Route path="/" element={<ProjectListPage />} />
            <Route path="/organizacao" element={<OrganizationPage />} />
            <Route path="/projects/:projectId" element={<ProjectLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="budget" element={<BudgetItemsPage />} />
              <Route path="purchases" element={<PurchaseProcessesPage />} />
              <Route path="purchases/:processId" element={<PurchaseProcessDetailPage />} />
              <Route path="personnel" element={<PersonnelPage />} />
              <Route path="revisions" element={<BudgetRevisionsPage />} />
              <Route path="revisions/:revisionId/edit" element={<BudgetRevisionEditorPage />} />
              <Route path="members" element={<ProjectMembersPage />} />
            </Route>
          </Routes>

          <HorunFooter moduleName="Horun · Financeiro" />
        </div>
      </CoordenadorProvider>
    </ThemeProvider>
  )
}
