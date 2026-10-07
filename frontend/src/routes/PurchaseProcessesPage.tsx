import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { budgetApi } from '../api/budget'
import { purchasesApi } from '../api/purchases'
import type { ItemBalance, PurchaseCategory } from '../types'
import type { PurchaseProcess } from '../types/purchase'
import { PURCHASE_STATUS_LABELS, TERMINAL_STATUSES } from '../types/purchase'
import { PurchaseStatusBadge } from '../components/purchases/PurchaseStatusBadge'
import { NewPurchaseProcessModal } from '../components/purchases/NewPurchaseProcessModal'
import { MoneyValue } from '../components/common/MoneyValue'
import { OverBalanceAlert } from '../components/purchases/OverBalanceAlert'
import type { ProjectContext } from './ProjectLayout'

const fieldStyle = { borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }
const muted = { color: 'var(--color-text-muted)' }

function normalize(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

export function PurchaseProcessesPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [processes, setProcesses] = useState<PurchaseProcess[] | null>(null)
  const [items, setItems] = useState<ItemBalance[]>([])
  const [categories, setCategories] = useState<PurchaseCategory[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)

  // Filtros guardados na URL (?tipo=&item=&status=&q=&concluidos=1): voltar
  // de um processo ou compartilhar o link mantém a mesma lista.
  const [params, setParams] = useSearchParams()
  const categoryFilter = params.get('tipo') ?? ''
  const itemFilter = params.get('item') ?? ''
  const statusFilter = params.get('status') ?? ''
  const search = params.get('q') ?? ''
  const showFinished = params.get('concluidos') === '1'
  const setFilter = (changes: Record<string, string>) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value)
          else next.delete(key)
        }
        return next
      },
      { replace: true },
    )

  const load = useCallback(() => {
    purchasesApi
      .list(project.id)
      .then(setProcesses)
      .catch((err) => setError(err.message))
    // Sem orçamento ativo o saldo dá 409 — a lista funciona assim mesmo,
    // só sem o tipo de despesa/item nos cartões.
    budgetApi.balance(project.id).then(setItems).catch(() => setItems([]))
    budgetApi.purchaseCategories(project.id).then(setCategories).catch(() => setCategories([]))
  }, [project.id])

  useEffect(() => {
    load()
  }, [load])

  const itemByPosition = useMemo(() => new Map(items.map((i) => [i.position_id, i])), [items])
  const labelByCategory = useMemo(() => new Map(categories.map((c) => [c.category, c.label])), [categories])
  // Só os tipos de despesa / itens que têm alguma compra entram nos filtros.
  const usedPositions = useMemo(() => new Set((processes ?? []).map((p) => p.budget_position_id)), [processes])
  const filterCategories = categories.filter((c) =>
    items.some((i) => i.category === c.category && usedPositions.has(i.position_id)),
  )
  const filterItems = items.filter((i) => i.category === categoryFilter && usedPositions.has(i.position_id))

  if (error) return <p className="p-6 text-red-600">Erro ao carregar processos: {error}</p>
  if (processes === null) return <p className="p-6">Carregando…</p>

  const query = normalize(search.trim())
  const visible = processes.filter((p) => {
    const item = itemByPosition.get(p.budget_position_id)
    // status escolhido no filtro vale mesmo se for concluído/cancelado
    if (statusFilter ? p.status !== statusFilter : !showFinished && TERMINAL_STATUSES.has(p.status)) return false
    if (categoryFilter && item?.category !== categoryFilter) return false
    if (itemFilter && String(p.budget_position_id) !== itemFilter) return false
    if (query) {
      const haystack = normalize([p.title, p.vendor ?? '', p.process_number ?? ''].join(' '))
      if (!haystack.includes(query)) return false
    }
    return true
  })
  const anyFilter = Boolean(categoryFilter || itemFilter || statusFilter || search)

  return (
    <div className="p-4 md:p-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm" style={muted}>
          <input
            type="checkbox"
            checked={showFinished}
            onChange={(e) => setFilter({ concluidos: e.target.checked ? '1' : '' })}
          />
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

      <div className="mb-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <select
          aria-label="Filtrar por tipo de despesa"
          className="w-full min-w-0 rounded-md border px-3 py-2 text-sm"
          style={fieldStyle}
          value={categoryFilter}
          onChange={(e) => setFilter({ tipo: e.target.value, item: '' })}
        >
          <option value="">Todos os tipos de despesa</option>
          {filterCategories.map((c) => (
            <option key={c.category} value={c.category}>
              {c.label}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar por item"
          className="w-full min-w-0 rounded-md border px-3 py-2 text-sm disabled:opacity-60"
          style={fieldStyle}
          value={itemFilter}
          disabled={!categoryFilter}
          onChange={(e) => setFilter({ item: e.target.value })}
        >
          <option value="">{categoryFilter ? 'Todos os itens' : 'Item (escolha o tipo antes)'}</option>
          {filterItems.map((i) => (
            <option key={i.position_id} value={String(i.position_id)}>
              Nº {i.item_number} — {i.description}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar por situação"
          className="w-full min-w-0 rounded-md border px-3 py-2 text-sm"
          style={fieldStyle}
          value={statusFilter}
          onChange={(e) => setFilter({ status: e.target.value })}
        >
          <option value="">Todas as situações</option>
          {Object.entries(PURCHASE_STATUS_LABELS).map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
        <input
          type="search"
          aria-label="Buscar compra"
          className="w-full min-w-0 rounded-md border px-3 py-2 text-sm"
          style={fieldStyle}
          value={search}
          onChange={(e) => setFilter({ q: e.target.value })}
          placeholder="Buscar título, fornecedor ou nº"
        />
      </div>

      {anyFilter && (
        <p className="mb-3 text-xs" style={muted}>
          {visible.length} {visible.length === 1 ? 'processo encontrado' : 'processos encontrados'} ·{' '}
          <button
            type="button"
            className="underline"
            style={{ color: 'var(--color-primary)' }}
            onClick={() => setFilter({ tipo: '', item: '', status: '', q: '' })}
          >
            limpar filtros
          </button>
        </p>
      )}

      {visible.length === 0 && (
        <p style={muted}>
          {anyFilter ? 'Nenhum processo com estes filtros.' : 'Nenhum processo de compra em andamento.'}
        </p>
      )}

      <div className="space-y-2">
        {visible.map((process) => {
          const item = itemByPosition.get(process.budget_position_id)
          return (
            <Link
              key={process.id}
              to={`/projects/${project.id}/purchases/${process.id}`}
              className="flex flex-col gap-2 rounded-lg border p-3 hover:opacity-90 md:flex-row md:items-center md:justify-between"
              style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
            >
              <div className="min-w-0">
                {item && (
                  <div className="break-words text-xs font-medium" style={muted}>
                    {labelByCategory.get(item.category) ?? item.category} · Item {item.item_number} —{' '}
                    {item.description}
                  </div>
                )}
                <div className="break-words font-medium" style={{ color: 'var(--color-text)' }}>
                  {process.title}
                </div>
                <div className="text-xs" style={muted}>
                  {process.vendor ?? 'Fornecedor a definir'}
                  {process.process_number ? ` · Processo ${process.process_number}` : ''}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3 md:shrink-0 md:gap-4">
                <OverBalanceAlert process={process} />
                <MoneyValue value={process.final_value ?? process.estimated_value} />
                <PurchaseStatusBadge status={process.status} />
              </div>
            </Link>
          )
        })}
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
