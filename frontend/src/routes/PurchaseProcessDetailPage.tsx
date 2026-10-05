import { useCallback, useEffect, useState } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import { purchasesApi } from '../api/purchases'
import type { PurchaseProcess, TransitionAction } from '../types/purchase'
import { TERMINAL_STATUSES } from '../types/purchase'
import { PurchaseStatusBadge } from '../components/purchases/PurchaseStatusBadge'
import { ActionPanel } from '../components/purchases/ActionPanel'
import { DocumentsSection } from '../components/purchases/DocumentsSection'
import { ProcessHistory } from '../components/purchases/ProcessHistory'
import { MoneyValue } from '../components/common/MoneyValue'
import { OverBalanceAlert } from '../components/purchases/OverBalanceAlert'
import type { ProjectContext } from './ProjectLayout'

export function PurchaseProcessDetailPage() {
  const { project } = useOutletContext<ProjectContext>()
  const { processId } = useParams()
  const [process, setProcess] = useState<PurchaseProcess | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    if (!processId) return
    purchasesApi
      .get(project.id, Number(processId))
      .then(setProcess)
      .catch((err) => setError(err.message))
  }, [project.id, processId])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <p className="p-6 text-red-600">Erro ao carregar processo: {error}</p>
  if (process === null) return <p className="p-6">Carregando…</p>

  const canUploadDocs = !TERMINAL_STATUSES.has(process.status)

  async function handleTransition(input: {
    action: TransitionAction
    reason?: string
    vendor?: string
    final_value?: string
    override_reason?: string
    confirm_over_balance?: boolean
  }) {
    await purchasesApi.transition(project.id, process!.id, input)
    load()
  }

  return (
    <div className="p-4 md:p-6">
      <Link
        to={`/projects/${project.id}/purchases`}
        className="mb-3 inline-flex min-h-10 items-center text-sm md:min-h-0"
        style={{ color: 'var(--color-text-muted)' }}
      >
        ← Voltar para compras
      </Link>

      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="break-words text-xl font-semibold" style={{ color: 'var(--color-text)' }}>
            {process.title}
          </h2>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
            {process.vendor ?? 'Fornecedor a definir'}
            {process.process_number ? ` · Processo ${process.process_number}` : ''}
          </p>
        </div>
        <PurchaseStatusBadge status={process.status} />
      </div>

      {process.origin === 'planilha_sem_numero' && (
        <p className="mb-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Lançamento da planilha de acompanhamento sem nº de processo COPPETEC (ex.: DOA, ressarcimento, passagem pela
          agência) — conta como realizado
          {process.realized_on ? ` em ${process.realized_on.split('-').reverse().join('/')}` : ''}.
        </p>
      )}
      {process.origin === 'drive_import' && (
        <p className="mb-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Criado a partir da pasta do drive
          {process.drive_rel_path ? (
            <>
              {' '}
              —{' '}
              <Link
                to={`/projects/${project.id}/drive?path=${encodeURIComponent(process.drive_rel_path)}`}
                style={{ color: 'var(--color-primary)' }}
              >
                abrir a pasta
              </Link>
            </>
          ) : null}
          . O estado foi inferido pelos arquivos que existiam; confira e corrija se preciso.
        </p>
      )}

      {process.previous_attempt_id && (
        <p className="mb-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Nova tentativa —{' '}
          <Link
            to={`/projects/${project.id}/purchases/${process.previous_attempt_id}`}
            style={{ color: 'var(--color-primary)' }}
          >
            ver tentativa anterior
          </Link>
        </p>
      )}

      {process.status === 'cancelado' && process.cancel_reason && (
        <p className="mb-4 rounded-md px-3 py-2 text-sm" style={{ background: '#fee2e2', color: '#b91c1c' }}>
          Cancelado: {process.cancel_reason}
        </p>
      )}
      {process.status === 'rejeitado' && process.cancel_reason && (
        <p className="mb-4 rounded-md px-3 py-2 text-sm" style={{ background: '#fee2e2', color: '#b91c1c' }}>
          Rejeitado pela COPPETEC: {process.cancel_reason}
        </p>
      )}

      {process.over_balance_confirmed_at && (
        <p className="mb-4">
          <OverBalanceAlert process={process} withLabel />
        </p>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Quantidade
          </div>
          <div style={{ color: 'var(--color-text)' }}>{process.quantity}</div>
        </div>
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Valor unitário estimado
          </div>
          <MoneyValue value={process.estimated_unit_value} />
        </div>
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Valor estimado
          </div>
          <MoneyValue value={process.estimated_value} />
        </div>
        <div>
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Valor final
          </div>
          {process.final_value ? <MoneyValue value={process.final_value} /> : <span>—</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
            Documentos
          </h3>
          <DocumentsSection
            projectId={project.id}
            processId={process.id}
            canUpload={canUploadDocs}
            canDelete={canUploadDocs}
            onChange={load}
          />
        </div>

        {/* celular: as ações vêm antes dos documentos, sem precisar rolar */}
        <div className="order-first lg:order-none">
          <ActionPanel
            process={process}
            isCoordenador={project.my_role === 'coordenador'}
            onTransition={handleTransition}
          />
        </div>
      </div>

      <ProcessHistory projectId={project.id} processId={process.id} refreshKey={process.updated_at} />
    </div>
  )
}
