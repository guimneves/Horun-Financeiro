import { useState } from 'react'
import { useCoordenadorSession } from '../../context/CoordenadorContext'

export function CoordenadorButton() {
  const { isElevated, login, logout } = useCoordenadorSession()
  const [showPrompt, setShowPrompt] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (isElevated) {
    return (
      <button
        type="button"
        onClick={logout}
        className="rounded-md px-3 py-1.5 text-sm font-medium"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text)' }}
      >
        Sair do modo coordenador
      </button>
    )
  }

  async function handleSubmit() {
    setSubmitting(true)
    setError(null)
    try {
      await login(password)
      setShowPrompt(false)
      setPassword('')
    } catch {
      setError('Senha incorreta.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!showPrompt) {
    return (
      <button
        type="button"
        onClick={() => setShowPrompt(true)}
        className="rounded-md px-3 py-1.5 text-sm font-medium"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}
      >
        Entrar como coordenador
      </button>
    )
  }

  return (
    <span className="flex items-center gap-1">
      <input
        type="password"
        autoFocus
        className="w-32 rounded-md border px-2 py-1 text-sm"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        placeholder="Senha"
      />
      <button type="button" onClick={handleSubmit} disabled={submitting} style={{ color: 'var(--color-primary)' }}>
        ok
      </button>
      <button
        type="button"
        onClick={() => {
          setShowPrompt(false)
          setError(null)
        }}
        style={{ color: 'var(--color-text-muted)' }}
      >
        x
      </button>
      {error && (
        <span className="text-xs" style={{ color: '#b91c1c' }}>
          {error}
        </span>
      )}
    </span>
  )
}
