import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { fundingApi, type InstallmentInput } from '../api/funding'
import { projectsApi } from '../api/projects'
import type { ProjectContext } from './ProjectLayout'

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }
const input = { borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }
const primaryButton = { background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }

export function ProjectSettingsPage() {
  const { project, reloadProject } = useOutletContext<ProjectContext>()
  const [driveFolder, setDriveFolder] = useState(project.drive_folder ?? '')
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
    <div className="max-w-3xl p-6">
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
          Pasta do projeto no drive
        </h3>
        <p className="mb-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Caminho da pasta do projeto a partir da raiz do drive configurada no servidor (ex.:
          "Guilherme - 25465 Maturação Artificial"). Deixe em branco para desligar.
        </p>
        <div className="flex gap-2">
          <input className="flex-1 rounded-md border px-3 py-2 text-sm" style={input} value={driveFolder} onChange={(e) => setDriveFolder(e.target.value)} />
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
              <div key={index} className="mb-2 flex items-center gap-2">
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
    </div>
  )
}
