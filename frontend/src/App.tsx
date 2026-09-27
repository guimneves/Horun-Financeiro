import { ThemeProvider, ThemeToggle, HorunFooter } from '@horun/design-system'
import { Route, Routes } from 'react-router-dom'
import { ProjectListPage } from './routes/ProjectListPage'
import { ProjectLayout } from './routes/ProjectLayout'
import { DashboardPage } from './routes/DashboardPage'
import { BudgetItemsPage } from './routes/BudgetItemsPage'
import { PurchaseProcessesPage } from './routes/PurchaseProcessesPage'
import { PurchaseProcessDetailPage } from './routes/PurchaseProcessDetailPage'

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
          </Route>
        </Routes>

        <HorunFooter moduleName="Horun · Financeiro" />
      </div>
    </ThemeProvider>
  )
}
