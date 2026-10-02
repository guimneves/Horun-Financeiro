import { useEffect, useState } from 'react'
import { agentApi, type AgentDevice, type EnrollCode } from '../api/agent'
import { ApiError } from '../api/client'

// Mesma janela que o servidor usa para considerar o agente conectado
// (online_window_seconds em app/agent_server/settings.py).
const ONLINE_WINDOW_MS = 120_000

const card = { borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }
const button = { borderColor: 'var(--color-border)', color: 'var(--color-text)' }

function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString('pt-BR') : '—'
}

function deviceState(d: AgentDevice): { label: string; color: string } {
  if (d.revoked_at) return { label: 'revogado', color: 'var(--color-text-muted)' }
  if (d.last_seen_at && Date.now() - new Date(d.last_seen_at).getTime() < ONLINE_WINDOW_MS)
    return { label: 'conectado', color: '#16a34a' }
  return { label: 'sem sinal', color: '#dc2626' }
}

/** Administração do Horun Agent do drive (mesmo painel do RE7S): gerar o
 * código de instalação, ver quais instalações estão conectadas e com que
 * versão, e revogar. Só o admin do Core enxerga — para os outros a listagem
 * responde 403 e o painel não aparece. */
export function AgentPanel() {
  const [devices, setDevices] = useState<AgentDevice[] | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [code, setCode] = useState<EnrollCode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function refresh() {
    agentApi
      .listDevices()
      .then((list) => {
        setDevices(list)
        setError(null)
      })
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) setForbidden(true)
        else setError(err instanceof Error ? err.message : 'Erro ao listar as instalações do agente.')
      })
  }

  useEffect(() => {
    refresh()
    // "visto por último" muda a cada consulta do agente (poucos segundos)
    const timer = window.setInterval(refresh, 15_000)
    return () => window.clearInterval(timer)
  }, [])

  if (forbidden) return null

  function generateCode() {
    setBusy(true)
    agentApi
      .createEnrollCode()
      .then(setCode)
      .catch((err) => setError(err instanceof Error ? err.message : 'Erro ao gerar o código.'))
      .finally(() => setBusy(false))
  }

  function revoke(d: AgentDevice) {
    const ok = window.confirm(
      `Revogar a instalação "${d.device_name}"? O agente desse PC para de receber tarefas na hora; ` +
        'para voltar, é preciso gerar um código novo e instalar de novo.',
    )
    if (!ok) return
    setBusy(true)
    agentApi
      .revokeDevice(d.id)
      .then(refresh)
      .catch((err) => setError(err instanceof Error ? err.message : 'Erro ao revogar.'))
      .finally(() => setBusy(false))
  }

  const sorted = [...(devices ?? [])].sort((a, b) => Number(!!a.revoked_at) - Number(!!b.revoked_at))

  return (
    <section className="rounded-lg border p-4" style={card}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold" style={{ color: 'var(--color-text)' }}>
            Horun Agent (drive)
          </h3>
          <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Usado quando o drive é lido pelo PC onde o OneDrive está sincronizado (MODULE_DRIVE_MODE=agent).
          </p>
        </div>
        <button
          type="button"
          onClick={generateCode}
          disabled={busy}
          className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
          style={button}
        >
          Gerar código de instalação
        </button>
      </div>

      {code && (
        <div className="mb-3 rounded-md border p-3 text-sm" style={{ borderColor: 'var(--color-border)' }}>
          <div style={{ color: 'var(--color-text)' }}>
            Código: <code className="select-all text-base font-semibold tracking-widest">{code.code}</code>
            {code.expires_at && (
              <span className="ml-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                vale até {formatDateTime(code.expires_at)}, uso único
              </span>
            )}
          </div>
          <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            No PC do OneDrive: coloque em <code>enroll_code</code> no <code>config.json</code> do agente e reinicie
            o agente — ele troca o código por um token permanente e apaga o código do arquivo.
          </p>
        </div>
      )}

      {error && (
        <p className="mb-2 rounded-md px-3 py-2 text-sm" style={{ background: '#fee2e2', color: '#b91c1c' }}>
          {error}
        </p>
      )}

      {devices === null && !error && (
        <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          carregando…
        </p>
      )}
      {devices !== null && sorted.length === 0 && (
        <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Nenhuma instalação. Gere um código e instale o agente no PC do OneDrive.
        </p>
      )}

      {sorted.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" style={{ color: 'var(--color-text)' }}>
            <thead style={{ color: 'var(--color-text-muted)' }}>
              <tr>
                <th className="p-2 font-normal">Instalação</th>
                <th className="p-2 font-normal">Estado</th>
                <th className="p-2 font-normal">Visto por último</th>
                <th className="p-2 font-normal">Versão</th>
                <th className="p-2 font-normal" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((d) => {
                const state = deviceState(d)
                return (
                  <tr
                    key={d.id}
                    className="border-t"
                    style={{ borderColor: 'var(--color-border)', opacity: d.revoked_at ? 0.55 : 1 }}
                  >
                    <td className="p-2 font-medium">{d.device_name}</td>
                    <td className="p-2">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: state.color }} />
                        {state.label}
                      </span>
                    </td>
                    <td className="whitespace-nowrap p-2">{formatDateTime(d.last_seen_at)}</td>
                    <td className="p-2">{d.agent_version ?? 'antiga (< 0.3)'}</td>
                    <td className="p-2 text-right">
                      {!d.revoked_at && (
                        <button
                          type="button"
                          onClick={() => revoke(d)}
                          disabled={busy}
                          className="text-xs hover:underline disabled:opacity-50"
                          style={{ color: '#dc2626' }}
                        >
                          revogar
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
