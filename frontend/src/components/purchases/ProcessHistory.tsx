import { useEffect, useState } from 'react'
import { fundingApi } from '../../api/funding'
import type { AuditEvent } from '../../types'

const ACTION_LABELS: Record<string, string> = {
  criado: 'Processo criado',
  criado_a_partir_do_drive: 'Criado a partir da pasta do drive',
  editado: 'Dados editados',
  avancar_cotacao: 'Avançou para cotação',
  solicitar_autorizacao: 'Solicitou autorização',
  autorizar: 'Autorizou a compra',
  rejeitar: 'Rejeitou',
  emitir_nota_fiscal: 'Registrou a nota fiscal',
  confirmar_recebimento: 'Confirmou o recebimento',
  concluir: 'Concluiu',
  cancelar: 'Cancelou',
  documento_enviado: 'Enviou documento',
  documento_removido: 'Removeu documento',
  documento_reclassificado: 'Mudou o tipo de um documento',
}

const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

function summarize(event: AuditEvent): string | null {
  if (!event.detail) return null
  try {
    const d = JSON.parse(event.detail) as Record<string, unknown>
    const parts: string[] = []
    if (d.motivo) parts.push(`Motivo: ${String(d.motivo)}`)
    if (d.requisito_dispensado) parts.push(`Requisito dispensado: ${String(d.requisito_dispensado)}`)
    if (d.arquivo) parts.push(String(d.arquivo))
    if (d.pasta) parts.push(`Pasta: ${String(d.pasta)}`)
    if (d.estado_inferido) parts.push(`Estado inferido: ${String(d.estado_inferido)}`)
    return parts.length > 0 ? parts.join(' · ') : null
  } catch {
    return null
  }
}

export function ProcessHistory({ projectId, processId, refreshKey }: { projectId: number; processId: number; refreshKey: unknown }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null)

  useEffect(() => {
    fundingApi
      .events(projectId, 'purchase_process', processId)
      .then(setEvents)
      .catch(() => setEvents([]))
  }, [projectId, processId, refreshKey])

  if (events === null || events.length === 0) return null

  return (
    <div className="mt-6">
      <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        Histórico
      </h3>
      <ul className="space-y-1">
        {events.map((event) => {
          const detail = summarize(event)
          return (
            <li key={event.id} className="text-sm" style={{ color: 'var(--color-text)' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>{dateTime.format(new Date(event.created_at))}</span>{' '}
              · {event.username} · {ACTION_LABELS[event.action] ?? event.action}
              {detail && (
                <span className="block text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {detail}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
