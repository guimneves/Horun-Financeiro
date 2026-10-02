import { useEffect, useState } from 'react'
import { Link, useOutletContext, useSearchParams } from 'react-router-dom'
import { driveApi } from '../api/drive'
import type { DriveBrowse, DriveStatus, ScanReport, SyncResult } from '../types/drive'
import { PURCHASE_STATUS_LABELS } from '../types/purchase'
import { MoneyValue } from '../components/common/MoneyValue'
import { FilePreviewModal, previewKind } from '../components/common/FilePreviewModal'
import type { ProjectContext } from './ProjectLayout'

const ACTION_LABELS: Record<string, string> = {
  criar: 'Criar',
  criar_da_planilha: 'Criar (só na planilha)',
  existe: 'Já existe',
  sem_item_no_orcamento: 'Item fora do orçamento',
  duplicado_na_pasta: 'Duplicado na pasta',
}

const SUMMARY_LABELS: [string, string][] = [
  ['processos_na_pasta', 'Processos nas pastas'],
  ['a_criar', 'A criar (com pasta)'],
  ['a_criar_so_planilha', 'A criar (só na planilha)'],
  ['ja_existentes', 'Já existentes'],
  ['sem_item_no_orcamento', 'Item fora do orçamento'],
  ['arquivos_novos', 'Arquivos a vincular'],
  ['sem_valor', 'Sem valor na planilha'],
  ['pastas_nao_reconhecidas', 'Pastas não reconhecidas'],
]

const fileSize = (bytes: number | null) =>
  bytes === null ? '' : bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }
const input = { borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }

export function DrivePage() {
  const { project } = useOutletContext<ProjectContext>()
  const isCoordenador = project.my_role === 'coordenador'
  const [status, setStatus] = useState<DriveStatus | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  function loadStatus() {
    setChecking(true)
    setStatusError(null)
    driveApi
      .status(project.id)
      .then(setStatus)
      .catch((err) => setStatusError(err instanceof Error ? err.message : 'Erro ao consultar o drive.'))
      .finally(() => setChecking(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadStatus, [project.id, project.drive_folder])

  if (statusError) return <p className="p-6" style={{ color: 'var(--color-danger, #d43b3b)' }}>{statusError}</p>
  if (status === null) return <p className="p-6">Carregando…</p>

  if (!status.available) {
    return (
      <div className="p-6">
        <h2 className="mb-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
          Drive do projeto
        </h2>
        <p style={{ color: 'var(--color-text-muted)' }}>
          {status.message ?? 'O drive não está disponível.'}{' '}
          {isCoordenador && status.configured && (status.mode !== 'agent' || !status.project_folder) && (
            <Link to={`/projects/${project.id}/settings`} style={{ color: 'var(--color-primary)' }}>
              Configurar a pasta do projeto
            </Link>
          )}
        </p>
        {status.mode === 'agent' && status.project_folder && (
          <button
            type="button"
            onClick={loadStatus}
            disabled={checking}
            className="mt-3 rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50"
            style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
          >
            {checking ? 'Verificando…' : 'Verificar de novo'}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="p-6">
      <h2 className="mb-1 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
        Drive do projeto
      </h2>
      <p className="mb-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        Pasta: {status.project_folder}. O programa só lê o drive — nunca grava, move ou apaga arquivos nele.
        {status.mode === 'agent' && (
          <>
            {' '}
            Lido pelo Horun Agent no PC onde o OneDrive está sincronizado — cada ação espera esse PC responder
            (alguns segundos).
          </>
        )}
      </p>
      {isCoordenador && <SyncPanel projectId={project.id} />}
      <Browser projectId={project.id} />
    </div>
  )
}

function SyncPanel({ projectId }: { projectId: number }) {
  const [ledgerPath, setLedgerPath] = useState('')
  const [report, setReport] = useState<ScanReport | null>(null)
  const [result, setResult] = useState<SyncResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('criar')
  const [showAll, setShowAll] = useState(false)

  async function handleScan() {
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const scanned = await driveApi.scan(projectId, ledgerPath.trim())
      setReport(scanned)
      // Se não há nada a criar, mostra tudo — uma lista vazia parece que deu errado.
      setFilter(scanned.summary.a_criar + scanned.summary.a_criar_so_planilha > 0 ? 'criar' : 'todos')
      setShowAll(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao ler as pastas.')
    } finally {
      setBusy(false)
    }
  }

  async function handleSync() {
    if (!report) return
    const toCreate = report.summary.a_criar + report.summary.a_criar_so_planilha
    if (!window.confirm(`Criar ${toCreate} processo(s) e vincular ${report.summary.arquivos_novos} arquivo(s)? Nada no drive é alterado.`)) return
    setBusy(true)
    setError(null)
    try {
      setResult(await driveApi.sync(projectId, ledgerPath.trim()))
      setReport(await driveApi.scan(projectId, ledgerPath.trim()))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao sincronizar.')
    } finally {
      setBusy(false)
    }
  }

  const rows = report?.processes.filter((p) => filter === 'todos' || (filter === 'criar' ? p.action.startsWith('criar') : p.action === filter)) ?? []
  const visibleRows = showAll ? rows : rows.slice(0, 50)
  const toCreate = report ? report.summary.a_criar + report.summary.a_criar_so_planilha : 0
  const nothingToDo = report !== null && toCreate === 0 && report.summary.arquivos_novos === 0

  return (
    <div className="mb-8 rounded-lg border p-4" style={card}>
      <h3 className="mb-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        Ler pastas e sincronizar
      </h3>
      <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Lê as pastas (Categoria / Item N / AAAA-NNNN) e mostra o que seria criado. Só grava depois que você confirmar.
        Informe a planilha de acompanhamento para trazer os valores.
      </p>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input
          className="min-w-64 flex-1 rounded-md border px-3 py-2 text-sm"
          style={input}
          placeholder="Planilha de valores (opcional), ex.: 0_Saldo por item/NOVA 25465 Acompanhamento de saldo_reformulação.xlsx"
          value={ledgerPath}
          onChange={(e) => setLedgerPath(e.target.value)}
        />
        <button
          type="button"
          disabled={busy}
          onClick={handleScan}
          className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          {busy && report === null ? 'Lendo…' : 'Ler pastas'}
        </button>
      </div>

      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      {result && (
        <p className="mb-3 rounded-md px-3 py-2 text-sm" style={{ background: '#dcfce7', color: '#166534' }}>
          Sincronizado: {result.processos_criados} processo(s) criado(s) e {result.arquivos_vinculados} arquivo(s) vinculado(s).
        </p>
      )}

      {report && (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {SUMMARY_LABELS.map(([key, label]) => (
              <div key={key} className="rounded-md border p-2" style={{ borderColor: 'var(--color-border)' }}>
                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {label}
                </div>
                <div className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
                  {report.summary[key] ?? 0}
                </div>
              </div>
            ))}
          </div>

          {report.summary.sem_valor > 0 && (
            <p className="mb-2 rounded-md px-3 py-2 text-sm" style={{ background: '#fef9c3', color: '#a16207' }}>
              {report.summary.sem_valor} processo(s) entrarão com valor zero por não terem valor na planilha — o saldo
              só fica correto depois que o valor for preenchido.
            </p>
          )}
          {report.ledger_skipped.length > 0 && (
            <details className="mb-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <summary className="cursor-pointer">
                {report.ledger_skipped.length} linha(s) da planilha não puderam ser usadas (o dinheiro delas NÃO entra)
              </summary>
              <ul className="ml-4 mt-1 list-disc">
                {report.ledger_skipped.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
          )}
          {report.ledger_unused.length > 0 && (
            <details className="mb-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <summary className="cursor-pointer">{report.ledger_unused.length} processo(s) da planilha sem pasta correspondente</summary>
              <p className="ml-4 mt-1">{report.ledger_unused.join(', ')}</p>
            </details>
          )}
          {report.unrecognized.length > 0 && (
            <details className="mb-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <summary className="cursor-pointer">
                {report.unrecognized.length} pasta(s) fora do padrão (não viram processo — você decide)
              </summary>
              <ul className="ml-4 mt-1 list-disc">
                {report.unrecognized.map((u) => (
                  <li key={u.path}>
                    {u.path} — {u.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="mb-2 mt-3 flex items-center gap-2 text-sm">
            <label style={{ color: 'var(--color-text-muted)' }}>Mostrar:</label>
            <select
              className="rounded-md border px-2 py-1 text-sm"
              style={input}
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value)
                setShowAll(false)
              }}
            >
              <option value="criar">A criar</option>
              <option value="existe">Já existentes</option>
              <option value="sem_item_no_orcamento">Item fora do orçamento</option>
              <option value="todos">Todos</option>
            </select>
            <span style={{ color: 'var(--color-text-muted)' }}>{rows.length} processo(s)</span>
          </div>

          <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
                  <th className="px-3 py-2 text-left font-medium">Processo</th>
                  <th className="px-3 py-2 text-left font-medium">Título</th>
                  <th className="px-3 py-2 text-left font-medium">Item</th>
                  <th className="px-3 py-2 text-left font-medium">Estado inferido</th>
                  <th className="px-3 py-2 text-right font-medium">Valor</th>
                  <th className="px-3 py-2 text-right font-medium">Arquivos</th>
                  <th className="px-3 py-2 text-left font-medium">Ação</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((p) => (
                  <tr key={p.folder} className="border-t" style={{ borderColor: 'var(--color-border)' }} title={p.warnings.join('\n')}>
                    <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
                      <Link to={`?path=${encodeURIComponent(p.folder)}`} style={{ color: 'var(--color-primary)' }}>
                        {p.process_number}
                      </Link>
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
                      {p.title}
                      {p.vendor ? <span style={{ color: 'var(--color-text-muted)' }}> · {p.vendor}</span> : null}
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                      {p.category} · Nº{p.item_number}
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                      {PURCHASE_STATUS_LABELS[p.inferred_status] ?? p.inferred_status}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {p.value_source === 'planilha' ? <MoneyValue value={p.value} /> : <span title="Sem valor">—</span>}
                    </td>
                    <td className="px-3 py-2 text-right" style={{ color: 'var(--color-text-muted)' }}>
                      {p.new_files}/{p.files_total}
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                      {ACTION_LABELS[p.action] ?? p.action}
                      {p.warnings.length > 0 ? ' ⚠' : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > visibleRows.length && (
            <button type="button" className="mt-2 text-sm" style={{ color: 'var(--color-primary)' }} onClick={() => setShowAll(true)}>
              Mostrar os {rows.length} processos
            </button>
          )}

          <div className="mt-4">
            <button
              type="button"
              disabled={busy || nothingToDo}
              onClick={handleSync}
              className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
            >
              {nothingToDo ? 'Nada a sincronizar' : `Sincronizar (${toCreate} processos, ${report.summary.arquivos_novos} arquivos)`}
            </button>
            <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              O estado de cada processo é uma inferência pelos arquivos que existem na pasta (autorização, nota fiscal,
              atestado). Depois de sincronizar, confira e corrija na tela do processo; tudo fica no histórico.
            </p>
          </div>
        </>
      )}
    </div>
  )
}

function Browser({ projectId }: { projectId: number }) {
  const [params, setParams] = useSearchParams()
  const path = params.get('path') ?? ''
  const [listing, setListing] = useState<DriveBrowse | null>(null)
  const [error, setError] = useState<string | null>(null)
  // arquivo aberto no leitor (sem baixar)
  const [viewing, setViewing] = useState<{ name: string; relPath: string } | null>(null)

  useEffect(() => {
    setError(null)
    driveApi
      .browse(projectId, path)
      .then(setListing)
      .catch((err) => setError(err.message))
  }, [projectId, path])

  const go = (next: string) => setParams(next ? { path: next } : {})
  const crumbs = path ? path.split('/') : []

  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        Consultar arquivos
      </h3>
      <div className="mb-2 flex flex-wrap items-center gap-1 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        <button type="button" onClick={() => go('')} style={{ color: 'var(--color-primary)' }}>
          Início
        </button>
        {crumbs.map((part, index) => (
          <span key={crumbs.slice(0, index + 1).join('/')}>
            {' / '}
            <button type="button" onClick={() => go(crumbs.slice(0, index + 1).join('/'))} style={{ color: 'var(--color-primary)' }}>
              {part}
            </button>
          </span>
        ))}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {listing && (
        <ul className="divide-y rounded-lg border" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
          {listing.entries.length === 0 && (
            <li className="px-3 py-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
              Pasta vazia.
            </li>
          )}
          {listing.entries.map((entry) => (
            <li key={entry.rel_path} className="flex items-center justify-between px-3 py-2 text-sm" style={{ borderColor: 'var(--color-border)' }}>
              {entry.is_dir ? (
                <button type="button" className="text-left" style={{ color: 'var(--color-primary)' }} onClick={() => go(entry.rel_path)}>
                  📁 {entry.name}
                </button>
              ) : (
                previewKind(entry.name) ? (
                  <button
                    type="button"
                    className="text-left"
                    style={{ color: 'var(--color-primary)' }}
                    title="Abrir para ler, sem baixar"
                    onClick={() => setViewing({ name: entry.name, relPath: entry.rel_path })}
                  >
                    📄 {entry.name}
                  </button>
                ) : (
                  <a href={driveApi.fileUrl(projectId, entry.rel_path)} style={{ color: 'var(--color-primary)' }}>
                    📄 {entry.name}
                  </a>
                )
              )}
              <span className="flex shrink-0 items-center gap-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {!entry.is_dir && (
                  <a href={driveApi.fileUrl(projectId, entry.rel_path)} title="Baixar" style={{ color: 'var(--color-text-muted)' }}>
                    baixar
                  </a>
                )}
                {fileSize(entry.size_bytes)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {viewing && (
        <FilePreviewModal
          filename={viewing.name}
          downloadUrl={driveApi.fileUrl(projectId, viewing.relPath)}
          kind={previewKind(viewing.name)!}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  )
}
