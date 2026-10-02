import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { purchasesApi } from '../api/purchases'
import type { PurchaseProcess } from '../types/purchase'
import { TERMINAL_STATUSES } from '../types/purchase'
import { PurchaseStatusBadge } from '../components/purchases/PurchaseStatusBadge'
import { NewPurchaseProcessModal } from '../components/purchases/NewPurchaseProcessModal'
import { MoneyValue } from '../components/common/MoneyValue'
import { OverBalanceAlert } from '../components/purchases/OverBalanceAlert'
import type { ProjectContext } from './ProjectLayout'

export function PurchaseProcessesPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [processes, setProcesses] = useState<PurchaseProcess[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [showFinished, setShowFinished] = useState(false)

  const load = useCallback(() => {
    purchasesApi
      .list(project.id)
      .then(setProcesses)
      .catch((err) => setError(err.message))
  }, [project.id])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <p className="p-6 text-red-600">Erro ao carregar processos: {error}</p>
  if (processes === null) return <p className="p-6">Carregando…</p>

  const visible = processes.filter((p) => showFinished || !TERMINAL_STATUSES.has(p.status))

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          <input type="checkbox" checked={showFinished} onChange={(e) => setShowFinished(e.target.checked)} />
          Mostrar concluídos/cancelados/rejeitados
        </label>
        <button
          type="button"
          onClick={() => setShowNew(true)}
          className="rounded-md px-4 py-2 text-sm font-medium"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          + Novo processo
        </button>
      </div>

      {visible.length === 0 && (
        <p style={{ color: 'var(--color-text-muted)' }}>Nenhum processo de compra em andamento.</p>
      )}

      <div className="space-y-2">
        {visible.map((process) => (
          <Link
            key={process.id}
            to={`/projects/${project.id}/purchases/${process.id}`}
            className="flex items-center justify-between rounded-lg border p-3 hover:opacity-90"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
          >
            <div>
              <div className="font-medium" style={{ color: 'var(--color-text)' }}>
                {process.title}
              </div>
              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {process.vendor ?? 'Fornecedor a definir'}
                {process.process_number ? ` · Processo ${process.process_number}` : ''}
              </div>
            </div>
            <div className="flex items-center gap-4">
              <OverBalanceAlert process={process} />
              <MoneyValue value={process.final_value ?? process.estimated_value} />
              <PurchaseStatusBadge status={process.status} />
            </div>
          </Link>
        ))}
      </div>

      {showNew && (
        <NewPurchaseProcessModal
          projectId={project.id}
          blockOnExceed={project.balance_policy === 'bloquear'}
          onClose={() => setShowNew(false)}
          onCreated={() => {
            setShowNew(false)
            load()
          }}
        />
      )}
    </div>
  )
}
