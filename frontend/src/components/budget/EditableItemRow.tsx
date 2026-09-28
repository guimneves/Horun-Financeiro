import { useState } from 'react'
import type { BudgetItem } from '../../types'
import { budgetApi } from '../../api/budget'
import { MoneyValue } from '../common/MoneyValue'

interface EditableItemRowProps {
  projectId: number
  revisionId: number
  item: BudgetItem
  editable: boolean
  onChanged: () => void
}

export function EditableItemRow({ projectId, revisionId, item, editable, onChanged }: EditableItemRowProps) {
  const [description, setDescription] = useState(item.description)
  // unit_value só vem null quando o backend redige valor (colaborador sem
  // sessão de coordenador) — esta linha só renderiza editável pra
  // coordenador, então na prática nunca é null aqui.
  const [unitValue, setUnitValue] = useState(item.unit_value ?? '')
  const [plannedQuantity, setPlannedQuantity] = useState(item.planned_quantity)

  async function save(patch: Record<string, string>) {
    await budgetApi.updateItem(projectId, revisionId, item.id, patch)
    onChanged()
  }

  async function handleDelete() {
    await budgetApi.deleteItem(projectId, revisionId, item.id)
    onChanged()
  }

  if (!editable) {
    return (
      <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
        <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
          {item.item_number}
        </td>
        <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
          {item.description}
        </td>
        <td className="px-3 py-2 text-right">
          <MoneyValue value={item.unit_value} />
        </td>
        <td className="px-3 py-2 text-right">{item.planned_quantity}</td>
        <td className="px-3 py-2 text-right">
          <MoneyValue value={item.planned_value} />
        </td>
      </tr>
    )
  }

  return (
    <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
      <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
        {item.item_number}
      </td>
      <td className="px-3 py-2">
        <input
          className="w-full rounded border px-2 py-1"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onBlur={() => description !== item.description && save({ description })}
        />
      </td>
      <td className="px-3 py-2">
        <input
          type="number"
          className="w-24 rounded border px-2 py-1 text-right"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={unitValue}
          onChange={(e) => setUnitValue(e.target.value)}
          onBlur={() => unitValue !== item.unit_value && save({ unit_value: unitValue })}
        />
      </td>
      <td className="px-3 py-2">
        <input
          type="number"
          className="w-20 rounded border px-2 py-1 text-right"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={plannedQuantity}
          onChange={(e) => setPlannedQuantity(e.target.value)}
          onBlur={() => plannedQuantity !== item.planned_quantity && save({ planned_quantity: plannedQuantity })}
        />
      </td>
      <td className="px-3 py-2 text-right">
        <MoneyValue value={item.planned_value} />
      </td>
      <td className="px-3 py-2 text-right">
        <button type="button" onClick={handleDelete} className="text-xs" style={{ color: '#b91c1c' }}>
          remover
        </button>
      </td>
    </tr>
  )
}
