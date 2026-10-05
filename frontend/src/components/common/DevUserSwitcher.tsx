import { useEffect, useState } from 'react'
import { knownUsersApi, type KnownUser } from '../../api/knownUsers'
import { getDevIdentity, setDevIdentity } from '../../lib/devIdentity'

const DEV_DEFAULT_ID = 'dev'
const MANUAL_OPTION = '__manual__'

// Só renderizado em `npm run dev` (ver App.tsx) — deixa trocar de identidade
// local pra ver o app como coordenador ou colaborador sem precisar do Horun
// Core nem editar o banco na mão.
export function DevUserSwitcher() {
  const [knownUsers, setKnownUsers] = useState<KnownUser[]>([])
  const [manualId, setManualId] = useState('')
  const [manualName, setManualName] = useState('')
  const [showManual, setShowManual] = useState(false)

  useEffect(() => {
    knownUsersApi.list().then(setKnownUsers).catch(() => setKnownUsers([]))
  }, [])

  const current = getDevIdentity()
  const currentValue = current?.userId ?? DEV_DEFAULT_ID

  function apply(userId: string, username: string) {
    setDevIdentity(userId === DEV_DEFAULT_ID ? null : { userId, username })
    window.location.reload()
  }

  function handleChange(value: string) {
    if (value === MANUAL_OPTION) {
      setShowManual(true)
      return
    }
    const known = knownUsers.find((u) => u.user_id === value)
    apply(value, known?.username ?? value)
  }

  function handleManualSubmit() {
    const id = manualId.trim()
    const name = manualName.trim() || id
    if (!id) return
    apply(id, name)
  }

  return (
    <div className="flex items-center gap-1">
      <span
        className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
        style={{ background: '#7c3aed', color: 'white' }}
        title="Só existe em desenvolvimento — nunca aparece em produção"
      >
        dev
      </span>
      {!showManual ? (
        <select
          className="max-w-[9rem] rounded-md border px-2 py-1 text-xs md:max-w-none"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
          value={currentValue}
          onChange={(e) => handleChange(e.target.value)}
        >
          <option value={DEV_DEFAULT_ID}>Ver como: dev (padrão)</option>
          {knownUsers
            .filter((u) => u.user_id !== DEV_DEFAULT_ID)
            .map((u) => (
              <option key={u.user_id} value={u.user_id}>
                Ver como: {u.username} ({u.user_id})
              </option>
            ))}
          <option value={MANUAL_OPTION}>+ Novo usuário de teste…</option>
        </select>
      ) : (
        <div className="flex items-center gap-1">
          <input
            className="w-24 rounded-md border px-2 py-1 text-xs"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            placeholder="id (ex.: u-maria)"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
          />
          <input
            className="w-28 rounded-md border px-2 py-1 text-xs"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            placeholder="nome de exibição"
            value={manualName}
            onChange={(e) => setManualName(e.target.value)}
          />
          <button
            type="button"
            onClick={handleManualSubmit}
            className="rounded-md px-2 py-1 text-xs font-medium"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            ok
          </button>
          <button
            type="button"
            onClick={() => setShowManual(false)}
            className="text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            x
          </button>
        </div>
      )}
    </div>
  )
}
