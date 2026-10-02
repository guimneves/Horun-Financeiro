import { useState } from 'react'
import { authApi } from '../api/auth'
import { AgentPanel } from '../components/AgentPanel'

export function OrganizationPage() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState<{ type: 'ok' | 'error'; text: string } | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    setMessage(null)
    if (next !== confirm) {
      setMessage({ type: 'error', text: 'A confirmação não bate com a nova senha.' })
      return
    }
    if (next.length < 6) {
      setMessage({ type: 'error', text: 'A nova senha precisa ter ao menos 6 caracteres.' })
      return
    }
    setSubmitting(true)
    try {
      await authApi.changePassword(current, next)
      setMessage({ type: 'ok', text: 'Senha alterada com sucesso.' })
      setCurrent('')
      setNext('')
      setConfirm('')
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Erro ao trocar a senha.' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-6">
    <div className="mx-auto max-w-md">
      <h2 className="mb-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
        Organização interna
      </h2>
      <p className="mb-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>
        A senha de coordenador é única para todo o módulo — trocar aqui vale pra todos os projetos, não só o que
        você estava vendo.
      </p>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Senha atual
          </label>
          <input
            type="password"
            className="w-full rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Nova senha
          </label>
          <input
            type="password"
            className="w-full rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium" style={{ color: 'var(--color-text)' }}>
            Confirmar nova senha
          </label>
          <input
            type="password"
            className="w-full rounded-md border px-3 py-2 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>

        {message && (
          <p
            className="rounded-md px-3 py-2 text-sm"
            style={
              message.type === 'ok'
                ? { background: '#dcfce7', color: '#15803d' }
                : { background: '#fee2e2', color: '#b91c1c' }
            }
          >
            {message.text}
          </p>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting || !current || !next || !confirm}
          className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          {submitting ? 'Trocando…' : 'Trocar senha'}
        </button>
      </div>
    </div>

    {/* só aparece para o admin do Core (a listagem dá 403 para os outros) */}
    <div className="mx-auto mt-8 max-w-3xl">
      <AgentPanel />
    </div>
    </div>
  )
}
