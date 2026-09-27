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
}

export function AssignmentRow({ projectId, assignment, isCoordenador, onChanged }: AssignmentRowProps) {
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

  return (
    <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
      <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
        {assignment.person_name}
      </td>
      <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
        {assignment.role_title}
      </td>
      <td className="px-3 py-2">
        <StatusBadge label={assignment.status === 'ativo' ? 'Ativo' : 'Encerrado'} tone={assignment.status === 'ativo' ? 'success' : 'neutral'} />
      </td>
      <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
        {assignment.start_date}
        {assignment.end_date ? ` – ${assignment.end_date}` : ''}
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
        <label className="cursor-pointer" style={{ color: 'var(--color-primary)' }}>
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
      </td>
      <td className="px-3 py-2 text-right text-xs">
        {isCoordenador && assignment.status === 'ativo' && (
          <>
            {closing ? (
              <span className="flex items-center gap-1">
                <input
                  type="date"
                  className="rounded-md border px-1 py-0.5 text-xs"
                  style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
                <button type="button" onClick={handleClose} style={{ color: 'var(--color-primary)' }}>
                  ok
                </button>
                <button type="button" onClick={() => setClosing(false)} style={{ color: 'var(--color-text-muted)' }}>
                  x
                </button>
              </span>
            ) : (
              <button type="button" onClick={() => setClosing(true)} style={{ color: '#b91c1c' }}>
                Encerrar
              </button>
            )}
          </>
        )}
      </td>
    </tr>
  )
}
