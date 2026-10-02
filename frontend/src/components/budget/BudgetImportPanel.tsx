import { useState } from 'react'
import { budgetApi, type BudgetImportPreview } from '../../api/budget'
import { MoneyValue } from '../common/MoneyValue'

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }
const input = { borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }

/** Importar o orçamento da aba "Saldo por Item" da planilha de
 * acompanhamento (pedido do usuário): primeiro a prévia (nada é gravado),
 * depois a importação como revisão NOVA em rascunho — conferir no editor e
 * só então ativar. */
export function BudgetImportPanel({
  projectId,
  onImported,
  onClose,
}: {
  projectId: number
  onImported: (revisionId: number) => void
  onClose: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [label, setLabel] = useState('Importada da planilha')
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10))
  const [preview, setPreview] = useState<BudgetImportPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handlePreview() {
    if (!file) return
    setBusy(true)
    setError(null)
    setPreview(null)
    try {
      setPreview(await budgetApi.importPreview(projectId, file))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao ler a planilha.')
    } finally {
      setBusy(false)
    }
  }

  async function handleImport() {
    if (!file || !preview || !effectiveDate) return
    setBusy(true)
    setError(null)
    try {
      const result = await budgetApi.importBudget(projectId, file, label.trim(), effectiveDate)
      onImported(result.revision.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao importar.')
    } finally {
      setBusy(false)
    }
  }

  const totalItems = preview?.categories.reduce((n, c) => n + c.count, 0) ?? 0

  return (
    <div className="mb-4 rounded-lg border p-4" style={card}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Importar orçamento da planilha
        </h3>
        <button type="button" onClick={onClose} className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Fechar
        </button>
      </div>
      <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Planilha de acompanhamento (.xlsx), aba "Saldo por Item" — ex. a da pasta <code>0_Saldo por item</code> do
        drive. Cada linha vira um item (categoria, nº, descrição, justificativa, V. unitário, quantidade e
        rendimentos). A Equipe Executora fica de fora (tela de Pessoal). Entra como uma revisão nova em rascunho:
        confira no editor e ative.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            Planilha
          </label>
          <input
            type="file"
            accept=".xlsx"
            className="text-sm"
            style={{ color: 'var(--color-text)' }}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null)
              setPreview(null)
            }}
          />
        </div>
        <button
          type="button"
          onClick={handlePreview}
          disabled={!file || busy}
          className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
          style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
        >
          {busy && !preview ? 'Lendo…' : 'Pré-visualizar'}
        </button>
      </div>

      {error && (
        <p className="mt-3 rounded-md px-3 py-2 text-sm" style={{ background: '#fee2e2', color: '#b91c1c' }}>
          {error}
        </p>
      )}

      {preview && (
        <div className="mt-4">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: 'var(--color-text-muted)' }}>
                <th className="py-1 text-left font-medium">Categoria</th>
                <th className="py-1 text-right font-medium">Itens</th>
                <th className="py-1 text-right font-medium">Valor previsto</th>
                <th className="py-1 text-right font-medium">Rendimentos</th>
              </tr>
            </thead>
            <tbody>
              {preview.categories.map((c) => (
                <tr key={c.category} className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                  <td className="py-1" style={{ color: 'var(--color-text)' }}>{c.label}</td>
                  <td className="py-1 text-right tabular-nums">{c.count}</td>
                  <td className="py-1 text-right tabular-nums"><MoneyValue value={c.planned_total} /></td>
                  <td className="py-1 text-right tabular-nums"><MoneyValue value={c.yield_total} /></td>
                </tr>
              ))}
            </tbody>
          </table>

          {preview.skipped_sections.length > 0 && (
            <p className="mt-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Fora da importação: {preview.skipped_sections.join('; ')}.
            </p>
          )}
          {preview.warnings.length > 0 && (
            <div className="mt-2 rounded-md px-3 py-2 text-xs" style={{ background: '#fef9c3', color: '#854d0e' }}>
              <div className="mb-1 font-medium">{preview.warnings.length} aviso(s) — confira antes de importar:</div>
              <ul className="list-disc pl-4">
                {preview.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-end gap-2">
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Rótulo da revisão
              </label>
              <input className="rounded-md border px-3 py-1.5 text-sm" style={input} value={label} onChange={(e) => setLabel(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
                Data de vigência
              </label>
              <input
                type="date"
                className="rounded-md border px-3 py-1.5 text-sm"
                style={input}
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
              />
            </div>
            <button
              type="button"
              onClick={handleImport}
              disabled={busy || totalItems === 0 || !effectiveDate}
              className="rounded-md px-4 py-1.5 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
            >
              {busy ? 'Importando…' : `Importar ${totalItems} itens como rascunho`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
