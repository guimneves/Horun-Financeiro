import { ThemeProvider, ThemeToggle, HorunFooter } from '@horun/design-system'
import { Route, Routes } from 'react-router-dom'
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
import { DrivePage } from './routes/DrivePage'
import { ProjectSettingsPage } from './routes/ProjectSettingsPage'

export default function App() {
  return (
    <ThemeProvider>
      <div className="flex min-h-screen flex-col">
        <header
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
        >
          <h1 className="text-lg font-semibold" style={{ color: 'var(--color-primary)' }}>
            Horun · Financeiro
          </h1>
          <ThemeToggle />
        </header>

        <Routes>
          <Route path="/" element={<ProjectListPage />} />
          <Route path="/projects/:projectId" element={<ProjectLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="budget" element={<BudgetItemsPage />} />
            <Route path="purchases" element={<PurchaseProcessesPage />} />
            <Route path="purchases/:processId" element={<PurchaseProcessDetailPage />} />
            <Route path="personnel" element={<PersonnelPage />} />
            <Route path="revisions" element={<BudgetRevisionsPage />} />
            <Route path="revisions/:revisionId/edit" element={<BudgetRevisionEditorPage />} />
            <Route path="members" element={<ProjectMembersPage />} />
            <Route path="drive" element={<DrivePage />} />
            <Route path="settings" element={<ProjectSettingsPage />} />
          </Route>
        </Routes>

        <HorunFooter moduleName="Horun · Financeiro" />
      </div>
    </ThemeProvider>
  )
}
