import { useEffect, useState } from 'react'
import { personnelApi } from '../../api/personnel'
import type { PersonnelAssignment } from '../../types/personnel'
import { MoneyValue } from '../common/MoneyValue'
import { StatusBadge } from '../common/StatusBadge'

interface AssignmentRowProps {
  projectId: number
  assignment: PersonnelAssignment
  isCoordenador: boolean
  onChanged: () => void
  /** "card" = celular: a linha da tabela vira um cartão */
  variant?: 'row' | 'card'
}

export function AssignmentRow({ projectId, assignment, isCoordenador, onChanged, variant = 'row' }: AssignmentRowProps) {
  const [closing, setClosing] = useState(false)
  const [endDate, setEndDate] = useState('')
  const [receiptCount, setReceiptCount] = useState<number | null>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    personnelApi.documents(projectId, assignment.id).then((docs) => setReceiptCount(docs.length))
  }, [projectId, assignment.id])

  async function handleClose() {
    if (!endDate) return
    await personnelApi.closeAssignment(projectId, assignment.id, endDate)
    setClosing(false)
    onChanged()
  }

  async function handleUploadReceipt(file: File) {
    setUploading(true)
    try {
      await personnelApi.uploadReceipt(projectId, assignment.id, file)
      const docs = await personnelApi.documents(projectId, assignment.id)
      setReceiptCount(docs.length)
    } finally {
      setUploading(false)
    }
  }

  const status = (
    <StatusBadge label={assignment.status === 'ativo' ? 'Ativo' : 'Encerrado'} tone={assignment.status === 'ativo' ? 'success' : 'neutral'} />
  )
  const period = `${assignment.start_date}${assignment.end_date ? ` – ${assignment.end_date}` : ''}`
  const receipts = (
    <label className="inline-flex min-h-10 cursor-pointer items-center md:min-h-0" style={{ color: 'var(--color-primary)' }}>
      {uploading ? 'Enviando…' : `Recibos (${receiptCount ?? '…'})`}
      <input
        type="file"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleUploadReceipt(file)
          e.target.value = ''
        }}
      />
    </label>
  )
  const closeControls =
    isCoordenador && assignment.status === 'ativo' ? (
      closing ? (
        <span className="flex items-center gap-1">
          <input
            type="date"
            className="rounded-md border px-1 py-0.5 text-xs"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
          <button type="button" onClick={handleClose} className="px-1" style={{ color: 'var(--color-primary)' }}>
            ok
          </button>
          <button type="button" onClick={() => setClosing(false)} className="px-1" style={{ color: 'var(--color-text-muted)' }}>
            x
          </button>
        </span>
      ) : (
        <button type="button" onClick={() => setClosing(true)} style={{ color: '#b91c1c' }}>
          Encerrar
        </button>
      )
    ) : null

  if (variant === 'card') {
    const money: [string, string | null][] = [
      ['Valor mensal', assignment.monthly_rate],
      ['Acumulado', assignment.accrued_value],
      ['Comprometido futuro', assignment.committed_future_value],
    ]
    return (
      <div className="rounded-lg border p-3" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="break-words font-medium" style={{ color: 'var(--color-text)' }}>
              {assignment.person_name}
            </div>
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              {assignment.role_title} · {period}
            </div>
          </div>
          {status}
        </div>
        <dl className="mt-2 space-y-0.5 text-sm">
          {money.map(([label, value]) => (
            <div key={label} className="flex justify-between gap-2">
              <dt style={{ color: 'var(--color-text-muted)' }}>{label}</dt>
              <dd className="tabular-nums">
                <MoneyValue value={value} />
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm">
          {receipts}
          {closeControls}
        </div>
      </div>
    )
  }

  return (
    <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
      <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
        {assignment.person_name}
      </td>
      <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
        {assignment.role_title}
      </td>
      <td className="px-3 py-2">{status}</td>
      <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
        {period}
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={assignment.monthly_rate} />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={assignment.accrued_value} />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={assignment.committed_future_value} />
      </td>
      <td className="px-3 py-2 text-right text-xs">
        {receipts}
      </td>
      <td className="px-3 py-2 text-right text-xs">
        {closeControls}
      </td>
    </tr>
  )
}
