import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import { purchasesApi } from '../api/purchases'
import type { ItemBalance } from '../types'
import type { PurchaseProcess } from '../types/purchase'
import { TERMINAL_STATUSES } from '../types/purchase'
import { MoneyValue } from '../components/common/MoneyValue'
import { AvailabilityBadge } from '../components/common/AvailabilityBadge'
import { PurchaseStatusBadge } from '../components/purchases/PurchaseStatusBadge'
import { NewPurchaseProcessModal } from '../components/purchases/NewPurchaseProcessModal'
import type { ProjectContext } from './ProjectLayout'

export function BudgetItemDetailPage() {
  const { project } = useOutletContext<ProjectContext>()
  const { positionId } = useParams()
  const navigate = useNavigate()
  const posId = Number(positionId)

  const [item, setItem] = useState<ItemBalance | null>(null)
  const [processes, setProcesses] = useState<PurchaseProcess[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [showFinished, setShowFinished] = useState(true)

  const load = useCallback(() => {
    budgetApi
      .balance(project.id)
      .then((rows) => setItem(rows.find((r) => r.position_id === posId) ?? null))
      .catch((err) => setError(err.message))
    purchasesApi
      .list(project.id, { positionId: posId })
      .then(setProcesses)
      .catch((err) => setError(err.message))
  }, [project.id, posId])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <p className="p-6 text-red-600">Erro ao carregar item: {error}</p>
  if (item === null || processes === null) return <p className="p-6">Carregando…</p>

  const visibleProcesses = processes.filter((p) => showFinished || !TERMINAL_STATUSES.has(p.status))

  return (
    <div className="p-6">
      <button
        type="button"
        onClick={() => navigate(`/projects/${project.id}/budget`)}
        className="mb-3 text-sm"
        style={{ color: 'var(--color-text-muted)' }}
      >
        ← Voltar para orçamento
      </button>

      <div className="mb-6 rounded-lg border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
        <div className="mb-1 text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
          {item.category} · Item Nº{item.item_number}
        </div>
        <h2 className="mb-3 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          {item.description}
        </h2>
        {item.coppetec_process_number && (
          <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Nº processo COPPETEC: {item.coppetec_process_number}
          </p>
        )}
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
          <dt style={{ color: 'var(--color-text-muted)' }}>Planejado</dt>
          <dd className="text-right sm:text-left">
            <MoneyValue value={item.planned_value} />
          </dd>
          <dt style={{ color: 'var(--color-text-muted)' }}>Comprometido</dt>
          <dd className="text-right sm:text-left">
            <MoneyValue value={item.committed} />
          </dd>
          <dt style={{ color: 'var(--color-text-muted)' }}>Realizado</dt>
          <dd className="text-right sm:text-left">
            <MoneyValue value={item.executed} />
          </dd>
          <dt className="font-medium" style={{ color: 'var(--color-text)' }}>
            Saldo
          </dt>
          <dd className="text-right sm:text-left">
            {item.balance === null ? (
              <AvailabilityBadge hasBalance={item.has_balance} />
            ) : (
              <MoneyValue value={item.balance} signColored />
            )}
          </dd>
        </dl>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Histórico de compras deste item
        </h3>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            <input type="checkbox" checked={showFinished} onChange={(e) => setShowFinished(e.target.checked)} />
            Mostrar concluídos/cancelados/rejeitados
          </label>
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="rounded-md px-3 py-1.5 text-sm font-medium"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            + Novo processo
          </button>
        </div>
      </div>

      {visibleProcesses.length === 0 && (
        <p style={{ color: 'var(--color-text-muted)' }}>Nenhum processo de compra para este item ainda.</p>
      )}

      <div className="space-y-2">
        {visibleProcesses.map((process) => (
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
          presetPositionId={posId}
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
