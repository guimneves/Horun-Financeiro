import { useState } from 'react'
import { useCoordenadorSession } from '../../context/CoordenadorContext'

export function CoordenadorButton() {
  const { isElevated, logout } = useCoordenadorSession()
  const [showModal, setShowModal] = useState(false)

  if (isElevated) {
    return (
      <div className="flex items-center gap-2">
        <span
          className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
          style={{ background: '#dcfce7', color: '#15803d' }}
        >
          <span aria-hidden>🔓</span> <span className="hidden sm:inline">Modo coordenador</span>
          <span className="sm:hidden">Coord.</span>
        </span>
        <button
          type="button"
          onClick={logout}
          className="text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Sair
        </button>
      </div>
    )
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setShowModal(true)}
        className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
      >
        <span aria-hidden>🔒</span> <span className="hidden sm:inline">Entrar como coordenador</span>
        <span className="sm:hidden">Coordenador</span>
      </button>
      {showModal && <CoordenadorLoginModal onClose={() => setShowModal(false)} />}
    </>
  )
}

function CoordenadorLoginModal({ onClose }: { onClose: () => void }) {
  const { login } = useCoordenadorSession()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit() {
    if (!password) return
    setSubmitting(true)
    setError(null)
    try {
      await login(password)
      onClose()
    } catch {
      setError('Senha incorreta.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="fin-modal-panel w-full max-w-sm rounded-lg border p-5"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
      >
        <div className="mb-1 flex items-center gap-2">
          <span aria-hidden className="text-lg">
            🔒
          </span>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
            Entrar como coordenador
          </h3>
        </div>
        <p className="mb-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Digite a senha compartilhada do módulo. Ela vale pra qualquer projeto que você já consiga abrir.
        </p>

        <input
          type="password"
          autoFocus
          className="mb-1 w-full rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="Senha de coordenador"
        />
        {error && (
          <p className="mb-2 text-sm" style={{ color: '#b91c1c' }}>
            {error}
          </p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-md px-4 py-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !password}
            className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            {submitting ? 'Entrando…' : 'Entrar'}
          </button>
        </div>
      </div>
    </div>
  )
}
