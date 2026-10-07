import { useEffect, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { fundingApi, type InstallmentInput } from '../api/funding'
import { projectsApi } from '../api/projects'
import { useCoordenadorSession } from '../context/CoordenadorContext'
import type { Project } from '../types'
import type { ProjectContext } from './ProjectLayout'

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }
const input = { borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }
const primaryButton = { background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }

/** Arquivar/desarquivar (coordenador) — a página toda já é só de coordenador. */
function ArchiveSection({ project, onDone }: { project: Project; onDone: (text: string) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const archived = Boolean(project.archived_at)

  async function toggle() {
    if (
      !archived &&
      !window.confirm(
        `Arquivar o projeto ${project.code}?\n\nEle sai da lista de projetos e da sincronização automática com o drive. ` +
          'Nenhum dado é apagado: o projeto continua abrindo por "Mostrar arquivados" e pode ser desarquivado a qualquer momento.',
      )
    )
      return
    setBusy(true)
    setError(null)
    try {
      await (archived ? projectsApi.unarchive(project.id) : projectsApi.archive(project.id))
      onDone(archived ? 'Projeto desarquivado.' : 'Projeto arquivado.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao arquivar.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="mb-6 rounded-lg border p-4" style={card}>
      <h3 className="mb-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
        Arquivar projeto
      </h3>
      <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        {archived
          ? `Arquivado em ${new Date(project.archived_at!).toLocaleDateString('pt-BR')}${project.archived_by ? ` por ${project.archived_by}` : ''}. Desarquivar volta o projeto à lista e à sincronização automática.`
          : 'Para projetos encerrados: sai da lista de projetos e da sincronização automática com o drive, mas todos os dados ficam e continuam abrindo. Dá para desarquivar quando quiser.'}
      </p>
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      <button
        type="button"
        disabled={busy}
        onClick={toggle}
        className="rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-text)' }}
      >
        {busy ? 'Salvando…' : archived ? 'Desarquivar projeto' : 'Arquivar projeto'}
      </button>
    </section>
  )
}

/** Excluir de vez — só o administrador máximo do Horun (nível 1); o backend confere. */
function DeleteSection({ project, onDeleted }: { project: Project; onDeleted: () => void }) {
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const matches = typed.trim() === project.code

  async function handleDelete() {
    if (!matches) return
    setBusy(true)
    setError(null)
    try {
      await projectsApi.remove(project.id, typed.trim())
      onDeleted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao excluir.')
      setBusy(false)
    }
  }

  return (
    <section className="mt-10 rounded-lg border p-4" style={{ borderColor: '#fca5a5', background: 'var(--color-bg-elevated)' }}>
      <h3 className="mb-1 text-sm font-semibold" style={{ color: '#b91c1c' }}>
        Excluir projeto
      </h3>
      <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Apaga <strong>para sempre</strong> todos os dados deste projeto no Financeiro: orçamento e revisões, compras,
        equipe, parcelas, participantes, histórico e os documentos anexados guardados no servidor. Não dá para desfazer —
        se a ideia é só tirar da lista, use "Arquivar".
      </p>
      <p className="mb-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Os arquivos da pasta do projeto no drive <strong>não</strong> são apagados.
      </p>
      <label className="mb-2 block text-xs" style={{ color: 'var(--color-text-muted)' }}>
        Digite o código do projeto ({project.code}) para confirmar
        <input
          className="mt-1 block w-full max-w-xs rounded-md border px-3 py-2 text-sm"
          style={input}
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoComplete="off"
        />
      </label>
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      <button
        type="button"
        disabled={!matches || busy}
        onClick={handleDelete}
        className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
        style={{ background: '#b91c1c', color: '#fff' }}
      >
        {busy ? 'Excluindo…' : 'Excluir projeto definitivamente'}
      </button>
    </section>
  )
}

export function ProjectSettingsPage() {
  const { project, reloadProject } = useOutletContext<ProjectContext>()
  const { me } = useCoordenadorSession()
  const navigate = useNavigate()
  const isSuperAdmin = me?.level === 1
  const [driveFolder, setDriveFolder] = useState(project.drive_folder ?? '')
  const [startDate, setStartDate] = useState(project.start_date ?? '')
  const [endDate, setEndDate] = useState(project.end_date ?? '')
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [installments, setInstallments] = useState<InstallmentInput[] | null>(null)

  useEffect(() => {
    fundingApi
      .installments(project.id)
      .then((list) => setInstallments(list.map((i) => ({ amount: i.amount, expected_date: i.expected_date, note: i.note }))))
      .catch(() => setInstallments([]))
  }, [project.id])

  async function save(action: () => Promise<unknown>, okText: string) {
    setMessage(null)
    try {
      await action()
      reloadProject()
      setMessage({ kind: 'ok', text: okText })
    } catch (err) {
      setMessage({ kind: 'error', text: err instanceof Error ? err.message : 'Erro ao salvar.' })
    }
  }

  const updateInstallment = (index: number, patch: Partial<InstallmentInput>) =>
    setInstallments((current) => (current ?? []).map((row, i) => (i === index ? { ...row, ...patch } : row)))

  return (
    <div className="max-w-3xl p-4 md:p-6">
      <h2 className="mb-4 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
        Configurações do projeto
      </h2>

      {message && (
        <p
          className="mb-4 rounded-md px-3 py-2 text-sm"
          style={message.kind === 'ok' ? { background: '#dcfce7', color: '#166534' } : { background: '#fee2e2', color: '#b91c1c' }}
        >
          {message.text}
        </p>
      )}

      <section className="mb-6 rounded-lg border p-4" style={card}>
        <h3 className="mb-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Vigência do projeto
        </h3>
        <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Início e fim do projeto — o Resumo compara o % do orçamento executado com o % do prazo já decorrido.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Início
            <input type="date" className="mt-1 block rounded-md border px-3 py-2 text-sm" style={input} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
          <label className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Fim
            <input type="date" className="mt-1 block rounded-md border px-3 py-2 text-sm" style={input} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
          <button
            type="button"
            className="rounded-md px-4 py-2 text-sm font-medium"
            style={primaryButton}
            onClick={() =>
              save(
                () => projectsApi.update(project.id, { start_date: startDate || null, end_date: endDate || null }),
                'Vigência salva.',
              )
            }
          >
            Salvar
          </button>
        </div>
      </section>

      <section className="mb-6 rounded-lg border p-4" style={card}>
        <h3 className="mb-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Pasta do projeto no drive
        </h3>
        <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Caminho da pasta do projeto a partir da raiz do drive configurada no servidor (ex.:
          "Guilherme - 25465 Maturação Artificial"). Deixe em branco para desligar.
        </p>
        <div className="flex flex-wrap gap-2">
          <input className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm" style={input} value={driveFolder} onChange={(e) => setDriveFolder(e.target.value)} />
          <button
            type="button"
            className="rounded-md px-4 py-2 text-sm font-medium"
            style={primaryButton}
            onClick={() => save(() => projectsApi.update(project.id, { drive_folder: driveFolder.trim() }), 'Pasta do drive salva.')}
          >
            Salvar
          </button>
        </div>
      </section>

      <section className="mb-6 rounded-lg border p-4" style={card}>
        <h3 className="mb-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Quando um valor não cabe no saldo do item
        </h3>
        {(['bloquear', 'avisar'] as const).map((policy) => (
          <label key={policy} className="mt-2 flex items-start gap-2 text-sm" style={{ color: 'var(--color-text)' }}>
            <input
              type="radio"
              name="balance_policy"
              checked={project.balance_policy === policy}
              onChange={() => save(() => projectsApi.update(project.id, { balance_policy: policy }), 'Política de saldo salva.')}
            />
            <span>
              <strong>{policy === 'bloquear' ? 'Bloquear' : 'Só avisar'}</strong>
              <span className="block text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {policy === 'bloquear'
                  ? 'Não deixa criar nem aumentar um processo acima do saldo. Histórico importado do drive nunca é bloqueado.'
                  : 'Deixa passar, mostra o aviso e o saldo do item fica negativo.'}
              </span>
            </span>
          </label>
        ))}
      </section>

      <section className="rounded-lg border p-4" style={card}>
        <h3 className="mb-1 text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Parcelas de repasse
        </h3>
        <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Usadas no resumo para mostrar quanto de cada parcela já foi utilizado.
        </p>
        {installments === null ? (
          <p className="text-sm">Carregando…</p>
        ) : (
          <>
            {installments.map((row, index) => (
              <div key={index} className="mb-2 flex flex-wrap items-center gap-2">
                <span className="w-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                  {index + 1}ª
                </span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="w-40 rounded-md border px-3 py-2 text-sm"
                  style={input}
                  placeholder="Valor (R$)"
                  value={row.amount}
                  onChange={(e) => updateInstallment(index, { amount: e.target.value })}
                />
                <input
                  type="date"
                  className="rounded-md border px-3 py-2 text-sm"
                  style={input}
                  value={row.expected_date ?? ''}
                  onChange={(e) => updateInstallment(index, { expected_date: e.target.value || null })}
                />
                <button
                  type="button"
                  className="text-xs"
                  style={{ color: '#b91c1c' }}
                  onClick={() => setInstallments((current) => (current ?? []).filter((_, i) => i !== index))}
                >
                  remover
                </button>
              </div>
            ))}
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                className="rounded-md px-3 py-1.5 text-sm"
                style={{ color: 'var(--color-primary)' }}
                onClick={() => setInstallments((current) => [...(current ?? []), { amount: '', expected_date: null }])}
              >
                + Adicionar parcela
              </button>
              <button
                type="button"
                className="rounded-md px-4 py-1.5 text-sm font-medium"
                style={primaryButton}
                onClick={() =>
                  save(
                    () => fundingApi.replaceInstallments(project.id, installments.filter((r) => r.amount !== '')),
                    'Parcelas salvas.',
                  )
                }
              >
                Salvar parcelas
              </button>
            </div>
          </>
        )}
      </section>

      <div className="mt-6">
        <ArchiveSection
          project={project}
          onDone={(text) => {
            reloadProject()
            setMessage({ kind: 'ok', text })
          }}
        />
      </div>

      {isSuperAdmin && (
        <DeleteSection
          project={project}
          onDeleted={() => {
            reloadProject()
            navigate('/', { replace: true })
          }}
        />
      )}
    </div>
  )
}
