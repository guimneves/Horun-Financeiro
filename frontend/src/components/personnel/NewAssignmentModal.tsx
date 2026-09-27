import { useEffect, useState } from 'react'
import { budgetApi } from '../../api/budget'
import { personnelApi } from '../../api/personnel'
import type { ItemBalance } from '../../types'
import type { Person } from '../../types/personnel'

interface NewAssignmentModalProps {
  projectId: number
  onClose: () => void
  onCreated: () => void
}

export function NewAssignmentModal({ projectId, onClose, onCreated }: NewAssignmentModalProps) {
  const [positions, setPositions] = useState<ItemBalance[] | null>(null)
  const [people, setPeople] = useState<Person[] | null>(null)
  const [positionId, setPositionId] = useState<number | null>(null)
  const [personId, setPersonId] = useState<number | 'new' | null>(null)
  const [newPersonName, setNewPersonName] = useState('')
  const [roleTitle, setRoleTitle] = useState('')
  const [monthlyRate, setMonthlyRate] = useState('')
  const [startDate, setStartDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    budgetApi.balance(projectId).then((items) => setPositions(items.filter((i) => i.category === 'equipe_executora')))
    personnelApi.listPeople(projectId).then(setPeople)
  }, [projectId])

  async function handleSubmit() {
    if (positionId === null || personId === null || !roleTitle.trim() || !monthlyRate || !startDate) return
    setSubmitting(true)
    setError(null)
    try {
      let finalPersonId = personId
      if (personId === 'new') {
        if (!newPersonName.trim()) throw new Error('Informe o nome da pessoa.')
        const person = await personnelApi.createPerson(projectId, newPersonName.trim())
        finalPersonId = person.id
      }
      await personnelApi.createAssignment(projectId, {
        person_id: finalPersonId as number,
        budget_position_id: positionId,
        role_title: roleTitle.trim(),
        monthly_rate: monthlyRate,
        start_date: startDate,
      })
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar atribuição.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="w-full max-w-md rounded-lg border p-5"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
      >
        <h3 className="mb-4 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Nova atribuição de pessoal
        </h3>

        <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          Item de orçamento (Equipe Executora)
        </label>
        <select
          className="mb-3 w-full rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={positionId ?? ''}
          onChange={(e) => setPositionId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Selecione…</option>
          {positions?.map((p) => (
            <option key={p.position_id} value={p.position_id}>
              Nº{p.item_number} — {p.description} (saldo {p.balance})
            </option>
          ))}
        </select>
        {positions !== null && positions.length === 0 && (
          <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Nenhum item de orçamento na categoria Equipe Executora ainda — crie um em "Orçamento" primeiro.
          </p>
        )}

        <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          Pessoa
        </label>
        <select
          className="mb-3 w-full rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={personId ?? ''}
          onChange={(e) => setPersonId(e.target.value === 'new' ? 'new' : e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Selecione…</option>
          {people?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.full_name}
            </option>
          ))}
          <option value="new">+ Nova pessoa…</option>
        </select>
        {personId === 'new' && (
          <input
            className="mb-3 w-full rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            placeholder="Nome completo"
            value={newPersonName}
            onChange={(e) => setNewPersonName(e.target.value)}
          />
        )}

        <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
          Cargo / função
        </label>
        <input
          className="mb-3 w-full rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          placeholder="Ex.: Bolsista Doutorado"
          value={roleTitle}
          onChange={(e) => setRoleTitle(e.target.value)}
        />

        <div className="mb-3 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              Valor mensal
            </label>
            <input
              type="number"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              value={monthlyRate}
              onChange={(e) => setMonthlyRate(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
              Início
            </label>
            <input
              type="date"
              className="w-full rounded-md border px-3 py-2 text-sm"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
        </div>

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            {submitting ? 'Criando…' : 'Criar atribuição'}
          </button>
        </div>
      </div>
    </div>
  )
}
