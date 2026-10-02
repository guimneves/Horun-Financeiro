import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  dashboardApi,
  type Dashboard,
  type DashboardAlert,
  type DashboardCategory,
  type DashboardTotals,
} from '../api/dashboard'
import { MoneyValue } from '../components/common/MoneyValue'
import type { ProjectContext } from './ProjectLayout'

// Cores das partes do previsto — fixas por significado, nunca pela posição.
const PARTS = [
  { key: 'executed_share', label: 'Realizado', color: '#2a78d6' },
  { key: 'committed_share', label: 'Comprometido', color: '#eda100' },
  { key: 'balance_share', label: 'Saldo', color: '#b8b6ad' },
  { key: 'overrun_share', label: 'Estouro', color: '#e34948' },
] as const

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }
const muted = { color: 'var(--color-text-muted)' }
const pct = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 })
const compactBrl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1 })

const share = (value: string | null) => (value === null ? null : Number(value))
const fmtPct = (value: string | null) => (value === null ? '—' : pct.format(Number(value)))

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border p-4" style={card}>
      <div className="text-xs" style={muted}>
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums" style={{ color: 'var(--color-text)' }}>
        {value}
      </div>
      {hint && (
        <div className="mt-0.5 text-xs" style={muted}>
          {hint}
        </div>
      )}
    </div>
  )
}

function KpiRow({ board }: { board: Dashboard }) {
  const t = board.total
  const money = (v: string | null) => (v === null ? '—' : compactBrl.format(Number(v)))
  const available = t.planned_value === null ? null : Number(t.planned_value) + Number(t.yield_amount ?? 0)
  const executed = share(t.executed_share)
  const elapsed = share(board.time_elapsed_share)
  let pace: string | undefined
  if (executed !== null && elapsed !== null) {
    const gap = Math.round((executed - elapsed) * 100)
    pace = gap === 0 ? 'no ritmo do prazo' : gap < 0 ? `${-gap} pontos abaixo do ritmo do prazo` : `${gap} pontos acima do ritmo do prazo`
  }
  return (
    <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label="Orçamento + rendimentos"
        value={available === null ? '100%' : compactBrl.format(available)}
        hint={board.values_visible ? `rendimentos: ${money(t.yield_amount)}` : 'valores visíveis só para o coordenador'}
      />
      <Kpi label="Realizado" value={board.values_visible ? money(t.executed) : fmtPct(t.executed_share)} hint={`${fmtPct(t.executed_share)} do orçamento`} />
      <Kpi label="Comprometido" value={board.values_visible ? money(t.committed) : fmtPct(t.committed_share)} hint="cotação e autorização em andamento" />
      <Kpi
        label="Prazo decorrido"
        value={elapsed === null ? '—' : pct.format(elapsed)}
        hint={elapsed === null ? 'defina início e fim em Configurações' : pace}
      />
    </div>
  )
}

function Legend() {
  return (
    <div className="mb-2 flex flex-wrap gap-4 text-xs" style={muted}>
      {PARTS.map((p) => (
        <span key={p.key} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: p.color }} />
          {p.label}
        </span>
      ))}
    </div>
  )
}

function CategoryChart({ categories }: { categories: DashboardCategory[] }) {
  // maior previsto primeiro: é onde está o dinheiro
  const rows = [...categories]
    .sort((a, b) => Number(b.planned_value ?? 0) - Number(a.planned_value ?? 0) || a.label.localeCompare(b.label))
    .map((c) => ({
      label: c.label,
      ...Object.fromEntries(PARTS.map((p) => [p.key, Math.round((share(c[p.key]) ?? 0) * 1000) / 10])),
    }))
  // escala fixa de 0 a 100%; só passa disso se alguma categoria estourou
  // (arredondamento de 100,1% não conta)
  const widest = Math.max(100, ...rows.map((r) => PARTS.reduce((sum, p) => sum + Number(r[p.key as keyof typeof r] ?? 0), 0)))
  const top = widest > 101 ? Math.ceil(widest / 25) * 25 : 100
  const ticks = Array.from({ length: top / 25 + 1 }, (_, i) => i * 25)
  return (
    <div style={{ width: '100%', height: Math.max(160, rows.length * 36 + 40) }}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke="var(--color-border)" />
          <XAxis
            type="number"
            domain={[0, top]}
            ticks={ticks}
            allowDataOverflow
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: 'var(--color-text-muted)', fontSize: 12 }}
            stroke="var(--color-border)"
          />
          <YAxis type="category" dataKey="label" width={210} tick={{ fill: 'var(--color-text)', fontSize: 12 }} stroke="var(--color-border)" />
          <Tooltip
            cursor={{ fill: 'var(--color-surface)' }}
            formatter={(value, name) => [`${value}%`, PARTS.find((p) => p.key === name)?.label ?? name]}
            contentStyle={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)', fontSize: 12 }}
          />
          {PARTS.map((p, i) => (
            <Bar key={p.key} dataKey={p.key} stackId="a" fill={p.color} maxBarSize={22} radius={i === PARTS.length - 1 ? [0, 3, 3, 0] : 0} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function SummaryCells({ row, visible }: { row: DashboardTotals; visible: boolean }) {
  const negative = row.balance !== null ? Number(row.balance) < 0 : Number(row.overrun_share ?? 0) > 0
  return (
    <>
      <td className="px-3 py-1.5 text-right tabular-nums">{visible ? <MoneyValue value={row.planned_value} /> : '—'}</td>
      <td className="px-3 py-1.5 text-right tabular-nums">{visible ? <MoneyValue value={row.yield_amount} /> : '—'}</td>
      <td className="px-3 py-1.5 text-right tabular-nums">{visible ? <MoneyValue value={row.executed} /> : fmtPct(row.executed_share)}</td>
      <td className="px-3 py-1.5 text-right tabular-nums">{visible ? <MoneyValue value={row.committed} /> : fmtPct(row.committed_share)}</td>
      <td className="px-3 py-1.5 text-right tabular-nums" style={negative ? { color: '#dc2626', fontWeight: 600 } : undefined}>
        {visible ? <MoneyValue value={row.balance} /> : negative ? `estouro ${fmtPct(row.overrun_share)}` : fmtPct(row.balance_share)}
      </td>
      <td className="px-3 py-1.5 text-right tabular-nums" style={muted}>
        {fmtPct(row.executed_share)}
      </td>
    </>
  )
}

/** O "Quadro Resumo" da planilha: categorias agrupadas em Capital e
 * Correntes, com subtotal de cada grupo e o total do projeto. */
function SummaryTable({ board, projectId }: { board: Dashboard; projectId: number }) {
  const visible = board.values_visible
  return (
    <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
      <table className="w-full text-sm" style={{ color: 'var(--color-text)' }}>
        <thead>
          <tr style={{ background: 'var(--color-surface)', ...muted }}>
            <th className="px-3 py-2 text-left font-medium">Elemento de despesa</th>
            <th className="px-3 py-2 text-right font-medium">Previsto</th>
            <th className="px-3 py-2 text-right font-medium">Rendimentos</th>
            <th className="px-3 py-2 text-right font-medium">Realizado</th>
            <th className="px-3 py-2 text-right font-medium">Comprometido</th>
            <th className="px-3 py-2 text-right font-medium">Saldo</th>
            <th className="px-3 py-2 text-right font-medium">% realizado</th>
          </tr>
        </thead>
        <tbody>
          {board.groups.map((group) => {
            const cats = board.categories.filter((c) => c.group === group.group)
            if (cats.length === 0) return null
            return [
              ...cats.map((c) => (
                <tr key={c.category} className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                  <td className="px-3 py-1.5">
                    <Link to={`/projects/${projectId}/budget?category=${c.category}`} style={{ color: 'var(--color-primary)' }}>
                      {c.label}
                    </Link>
                    <span className="ml-1 text-xs" style={muted}>
                      ({c.items} {c.items === 1 ? 'item' : 'itens'})
                    </span>
                  </td>
                  <SummaryCells row={c} visible={visible} />
                </tr>
              )),
              <tr key={`sub-${group.group}`} className="border-t font-medium" style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
                <td className="px-3 py-1.5">{group.label}</td>
                <SummaryCells row={group} visible={visible} />
              </tr>,
            ]
          })}
          <tr className="border-t-2 font-semibold" style={{ borderColor: 'var(--color-border)' }}>
            <td className="px-3 py-2">Total do projeto</td>
            <SummaryCells row={board.total} visible={visible} />
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function Installments({ board }: { board: Dashboard }) {
  if (board.installments.length === 0) {
    return (
      <p className="text-sm" style={muted}>
        Nenhuma parcela cadastrada — cadastre em Configurações para acompanhar o uso de cada uma.
      </p>
    )
  }
  return (
    <div className="space-y-3">
      {board.installments.map((inst) => {
        const used = share(inst.utilization)
        return (
          <div key={inst.number}>
            <div className="flex justify-between text-sm" style={{ color: 'var(--color-text)' }}>
              <span>{inst.number}ª parcela</span>
              <span className="tabular-nums" style={muted}>
                {used === null ? '—' : pct.format(used)}
              </span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full border" style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
              <div className="h-full" style={{ width: `${Math.min(100, (used ?? 0) * 100)}%`, background: '#2a78d6' }} />
            </div>
            <div className="mt-0.5 text-xs" style={muted}>
              {inst.amount !== null && <MoneyValue value={inst.amount} />}
              {inst.expected_date && <> · prevista para {inst.expected_date.split('-').reverse().join('/')}</>}
              {used === null && ' · a anterior ainda não foi toda usada'}
            </div>
          </div>
        )
      })}
    </div>
  )
}

const ALERT_STYLE: Record<DashboardAlert['severity'], { border: string; icon: string; color: string }> = {
  danger: { border: '#fca5a5', icon: '⚠', color: '#b91c1c' },
  warning: { border: '#fcd34d', icon: '●', color: '#a16207' },
  info: { border: 'var(--color-border)', icon: 'ℹ', color: 'var(--color-text-muted)' },
}

function Alerts({ alerts, projectId }: { alerts: DashboardAlert[]; projectId: number }) {
  const [showAll, setShowAll] = useState(false)
  if (alerts.length === 0) {
    return (
      <p className="text-sm" style={muted}>
        Nada fora do normal — nenhum item estourado, perto do fim ou compra parada.
      </p>
    )
  }
  const shown = showAll ? alerts : alerts.slice(0, 8)
  return (
    <div className="space-y-2">
      {shown.map((a, i) => {
        const style = ALERT_STYLE[a.severity]
        const target = a.process_id
          ? `/projects/${projectId}/purchases/${a.process_id}`
          : a.category
            ? `/projects/${projectId}/budget?category=${a.category}`
            : null
        const body = (
          <>
            <span aria-hidden="true" style={{ color: style.color }}>
              {style.icon}
            </span>
            <span className="flex-1">{a.message}</span>
            {a.amount !== null && a.kind === 'saldo_negativo' && (
              <span className="tabular-nums font-medium" style={{ color: style.color }}>
                <MoneyValue value={a.amount} />
              </span>
            )}
          </>
        )
        return target ? (
          <Link key={i} to={target} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:opacity-90" style={{ borderColor: style.border, color: 'var(--color-text)' }}>
            {body}
          </Link>
        ) : (
          <div key={i} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm" style={{ borderColor: style.border, color: 'var(--color-text)' }}>
            {body}
          </div>
        )
      })}
      {alerts.length > 8 && (
        <button type="button" onClick={() => setShowAll((v) => !v)} className="text-sm" style={{ color: 'var(--color-primary)' }}>
          {showAll ? 'Mostrar menos' : `Mostrar todos (${alerts.length})`}
        </button>
      )}
    </div>
  )
}

/** Aba Resumo (pedido do usuário: "parecido com a planilha, com gráficos"):
 * indicadores, uso do orçamento por categoria, o Quadro Resumo, parcelas e
 * o que precisa de atenção. Colaborador vê tudo em percentuais. */
export function DashboardPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [board, setBoard] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    dashboardApi
      .get(project.id)
      .then(setBoard)
      .catch((err) => setError(err instanceof Error ? err.message : 'Erro ao carregar o resumo.'))
  }, [project.id])

  if (project.active_revision_id === null) {
    return (
      <p className="p-6" style={muted}>
        Este projeto ainda não tem uma revisão orçamentária ativa — importe ou crie uma em "Revisões" e ative-a.
      </p>
    )
  }
  if (error) return <p className="p-6 text-red-600">Erro ao carregar o resumo: {error}</p>
  if (board === null) return <p className="p-6">Carregando…</p>

  const sectionTitle = 'mb-3 text-sm font-semibold uppercase tracking-wide'
  return (
    <div className="p-6">
      <KpiRow board={board} />

      <section className="mb-6 rounded-lg border p-4" style={card}>
        <h3 className={sectionTitle} style={muted}>
          Uso do orçamento por categoria
        </h3>
        <Legend />
        <CategoryChart categories={board.categories} />
      </section>

      <section className="mb-6">
        <h3 className={sectionTitle} style={muted}>
          Quadro resumo
        </h3>
        <SummaryTable board={board} projectId={project.id} />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section className="rounded-lg border p-4" style={card}>
          <h3 className={sectionTitle} style={muted}>
            Parcelas recebidas × usadas
          </h3>
          <Installments board={board} />
        </section>
        <section className="rounded-lg border p-4" style={card}>
          <h3 className={sectionTitle} style={muted}>
            Precisa de atenção
          </h3>
          <Alerts alerts={board.alerts} projectId={project.id} />
        </section>
      </div>
    </div>
  )
}
