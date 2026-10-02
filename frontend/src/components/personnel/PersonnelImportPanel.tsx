import { useState } from 'react'
import { personnelApi, type PersonnelImportPreview } from '../../api/personnel'
import { MoneyValue } from '../common/MoneyValue'
import { uploadErrorMessage } from '../../lib/uploadError'

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }

const formatDate = (iso: string | null) => (iso ? iso.split('-').reverse().join('/') : '—')

/** Importar quem ocupa cada vaga, da aba "Equipe Executora" da planilha
 * de acompanhamento (pedido do usuário). As vagas vêm do orçamento —
 * importe o orçamento antes (Revisões → Importar da planilha). */
export function PersonnelImportPanel({
  projectId,
  onImported,
  onClose,
}: {
  projectId: number
  onImported: () => void
  onClose: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<PersonnelImportPreview | null>(null)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handlePreview() {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    setPreview(null)
    try {
      setPreview(await personnelApi.importPreview(projectId, file))
    } catch (err) {
      setError(uploadErrorMessage(err, 'Erro ao ler a planilha.'))
    } finally {
      setBusy(false)
    }
  }

  async function handleImport() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const done = await personnelApi.importPersonnel(projectId, file)
      setResult(
        `${done.assignments_created} atribuição(ões) e ${done.people_created} pessoa(s) cadastradas` +
          (done.skipped ? `; ${done.skipped} linha(s) já existiam ou ficaram de fora.` : '.'),
      )
      setPreview(await personnelApi.importPreview(projectId, file))
      onImported()
    } catch (err) {
      setError(uploadErrorMessage(err, 'Erro ao importar.'))
    } finally {
      setBusy(false)
    }
  }

  const toCreate = preview?.rows.filter((r) => r.position_found && !r.already_imported).length ?? 0
  const missing = preview?.rows.filter((r) => !r.position_found) ?? []

  return (
    <div className="mb-4 rounded-lg border p-4" style={card}>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Importar equipe da planilha
        </h3>
        <button type="button" onClick={onClose} className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Fechar
        </button>
      </div>
      <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Aba "Equipe Executora" da planilha de acompanhamento: quem ocupa cada vaga, situação (ativo/encerrado),
        início, fim e valor mensal. As vagas precisam existir no orçamento — importe-o antes em Revisões →
        Importar da planilha. Pode importar de novo: quem já foi cadastrado não se repete.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <input
          type="file"
          accept=".xlsx"
          className="text-sm"
          style={{ color: 'var(--color-text)' }}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null)
            setPreview(null)
            setResult(null)
          }}
        />
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
      {result && (
        <p className="mt-3 rounded-md px-3 py-2 text-sm" style={{ background: '#dcfce7', color: '#15803d' }}>
          {result}
        </p>
      )}

      {preview && (
        <div className="mt-4">
          <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Realizado segundo a planilha: <MoneyValue value={preview.sheet_total} /> · calculado pelo módulo até hoje:{' '}
            <MoneyValue value={preview.accrued_total} /> (a planilha conta até a data em que foi atualizada; o módulo,
            até hoje).
          </p>
          <div className="max-h-80 overflow-auto rounded border" style={{ borderColor: 'var(--color-border)' }}>
            <table className="w-full text-sm">
              <thead className="sticky top-0" style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                <tr>
                  <th className="px-2 py-1 text-left font-medium">Vaga</th>
                  <th className="px-2 py-1 text-left font-medium">Pessoa</th>
                  <th className="px-2 py-1 text-left font-medium">Situação</th>
                  <th className="px-2 py-1 text-left font-medium">Início</th>
                  <th className="px-2 py-1 text-left font-medium">Fim</th>
                  <th className="px-2 py-1 text-right font-medium">Mensal</th>
                  <th className="px-2 py-1 text-right font-medium">Planilha</th>
                  <th className="px-2 py-1 text-right font-medium">Módulo (hoje)</th>
                  <th className="px-2 py-1 text-left font-medium" />
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r) => (
                  <tr key={r.sheet_row} className="border-t" style={{ borderColor: 'var(--color-border)', opacity: r.position_found ? 1 : 0.6 }}>
                    <td className="px-2 py-1" title={r.role_title}>
                      {r.item_number} · {r.role_title}
                    </td>
                    <td className="px-2 py-1">{r.person_name}</td>
                    <td className="px-2 py-1">{r.status === 'ativo' ? 'Ativo' : 'Encerrado'}</td>
                    <td className="px-2 py-1 tabular-nums">{formatDate(r.start_date)}</td>
                    <td className="px-2 py-1 tabular-nums">{formatDate(r.end_date)}</td>
                    <td className="px-2 py-1 text-right tabular-nums"><MoneyValue value={r.monthly_rate} /></td>
                    <td className="px-2 py-1 text-right tabular-nums"><MoneyValue value={r.sheet_value} /></td>
                    <td className="px-2 py-1 text-right tabular-nums"><MoneyValue value={r.accrued_value} /></td>
                    <td className="px-2 py-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {!r.position_found ? 'vaga fora do orçamento' : r.already_imported ? 'já cadastrada' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {(preview.warnings.length > 0 || missing.length > 0) && (
            <div className="mt-2 rounded-md px-3 py-2 text-xs" style={{ background: '#fef9c3', color: '#854d0e' }}>
              <ul className="list-disc pl-4">
                {missing.length > 0 && (
                  <li>
                    {missing.length} linha(s) com vaga que não existe no orçamento — ficam de fora (importe ou cadastre
                    a vaga antes).
                  </li>
                )}
                {preview.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <button
            type="button"
            onClick={handleImport}
            disabled={busy || toCreate === 0}
            className="mt-3 rounded-md px-4 py-1.5 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            {busy ? 'Importando…' : toCreate > 0 ? `Importar ${toCreate} atribuição(ões)` : 'Nada novo para importar'}
          </button>
        </div>
      )}
    </div>
  )
}
