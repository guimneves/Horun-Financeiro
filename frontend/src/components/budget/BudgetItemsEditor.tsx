import { useState } from 'react'
import { budgetApi } from '../../api/budget'
import type { BudgetItem, Category } from '../../types'
import { EditableItemRow } from './EditableItemRow'

interface BudgetItemsEditorProps {
  projectId: number
  revisionId: number
  items: BudgetItem[]
  categories: Category[]
  editable: boolean
  onChanged: () => void
}

// Lista de itens agrupada por categoria de despesa, com CRUD inline quando
// `editable` — reusado tanto pelo editor de revisão quanto pela aba
// Orçamento (enquanto há um rascunho aberto).
export function BudgetItemsEditor({ projectId, revisionId, items, categories, editable, onChanged }: BudgetItemsEditorProps) {
  const [newItem, setNewItem] = useState<{
    category: string
    itemNumber: string
    description: string
    unitValue: string
    quantity: string
    coppetecProcessNumber: string
  } | null>(null)

  async function handleAddItem() {
    if (!newItem) return
    await budgetApi.createItem(projectId, revisionId, {
      category: newItem.category,
      item_number: Number(newItem.itemNumber),
      description: newItem.description,
      unit_value: newItem.unitValue,
      planned_quantity: newItem.quantity,
      coppetec_process_number: newItem.coppetecProcessNumber || undefined,
    })
    setNewItem(null)
    onChanged()
  }

  return (
    <>
      {categories.map((category) => {
        const categoryItems = items.filter((i) => i.category === category.code)
        if (categoryItems.length === 0 && (!editable || newItem?.category !== category.code)) return null
        return (
          <div key={category.code} className="mb-6">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
                {category.label}
              </h3>
              {editable && (
                <button
                  type="button"
                  onClick={() =>
                    setNewItem({
                      category: category.code,
                      itemNumber: '',
                      description: '',
                      unitValue: '',
                      quantity: '',
                      coppetecProcessNumber: '',
                    })
                  }
                  className="text-xs"
                  style={{ color: 'var(--color-primary)' }}
                >
                  + item
                </button>
              )}
            </div>
            <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                    <th className="px-3 py-2 text-left font-medium">Nº</th>
                    <th className="px-3 py-2 text-left font-medium">Descrição</th>
                    <th className="px-3 py-2 text-right font-medium">V. Unit.</th>
                    <th className="px-3 py-2 text-right font-medium">Qtd.</th>
                    <th className="px-3 py-2 text-right font-medium">Valor</th>
                    <th className="px-3 py-2 text-left font-medium">Nº processo COPPETEC</th>
                    {editable && <th className="px-3 py-2"></th>}
                  </tr>
                </thead>
                <tbody>
                  {categoryItems.map((item) => (
                    <EditableItemRow
                      key={item.id}
                      projectId={projectId}
                      revisionId={revisionId}
                      item={item}
                      editable={editable}
                      onChanged={onChanged}
                    />
                  ))}
                  {editable && newItem?.category === category.code && (
                    <tr className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                      <td className="px-2 py-1">
                        <input
                          type="number"
                          className="w-14 rounded border px-1 py-1"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          value={newItem.itemNumber}
                          onChange={(e) => setNewItem({ ...newItem, itemNumber: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          className="w-full rounded border px-2 py-1"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          placeholder="Descrição"
                          value={newItem.description}
                          onChange={(e) => setNewItem({ ...newItem, description: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          type="number"
                          className="w-24 rounded border px-2 py-1 text-right"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          value={newItem.unitValue}
                          onChange={(e) => setNewItem({ ...newItem, unitValue: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          type="number"
                          className="w-20 rounded border px-2 py-1 text-right"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          value={newItem.quantity}
                          onChange={(e) => setNewItem({ ...newItem, quantity: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1"></td>
                      <td className="px-2 py-1">
                        <input
                          className="w-28 rounded border px-2 py-1"
                          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
                          placeholder="Nº processo"
                          value={newItem.coppetecProcessNumber}
                          onChange={(e) => setNewItem({ ...newItem, coppetecProcessNumber: e.target.value })}
                        />
                      </td>
                      <td className="px-2 py-1 text-right">
                        <button type="button" onClick={handleAddItem} style={{ color: 'var(--color-primary)' }}>
                          salvar
                        </button>{' '}
                        <button type="button" onClick={() => setNewItem(null)} style={{ color: 'var(--color-text-muted)' }}>
                          x
                        </button>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )
      })}
    </>
  )
}
