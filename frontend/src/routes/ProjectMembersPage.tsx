import { useCallback, useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { projectsApi, type Membership } from '../api/projects'
import { StatusBadge } from '../components/common/StatusBadge'
import type { ProjectContext } from './ProjectLayout'

export function ProjectMembersPage() {
  const { project } = useOutletContext<ProjectContext>()
  const [members, setMembers] = useState<Membership[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [userId, setUserId] = useState('')
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<'coordenador' | 'colaborador'>('colaborador')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(() => {
    projectsApi
      .members(project.id)
      .then(setMembers)
      .catch((err) => setError(err.message))
  }, [project.id])

  useEffect(() => {
    load()
  }, [load])

  async function handleAdd() {
    if (!userId.trim() || !username.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await projectsApi.addMember(project.id, { user_id: userId.trim(), username: username.trim(), role })
      setUserId('')
      setUsername('')
      setRole('colaborador')
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao adicionar membro.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRemove(membershipId: number) {
    await projectsApi.removeMember(project.id, membershipId)
    load()
  }

  if (members === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="p-6">
      <h2 className="mb-4 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
        Membros do projeto
      </h2>

      <div
        className="mb-6 flex flex-wrap items-end gap-2 rounded-lg border p-4"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
      >
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            ID do usuário (X-Horun-User-Id do Core)
          </label>
          <input
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            Nome de exibição
          </label>
          <input
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
            Papel
          </label>
          <select
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
            value={role}
            onChange={(e) => setRole(e.target.value as 'coordenador' | 'colaborador')}
          >
            <option value="colaborador">Colaborador</option>
            <option value="coordenador">Coordenador</option>
          </select>
        </div>
        <button
          type="button"
          onClick={handleAdd}
          disabled={submitting}
          className="rounded-md px-4 py-1.5 text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          {submitting ? 'Adicionando…' : '+ Adicionar'}
        </button>
      </div>

      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: 'var(--color-border)' }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)' }}>
              <th className="px-3 py-2 text-left font-medium">Nome</th>
              <th className="px-3 py-2 text-left font-medium">ID</th>
              <th className="px-3 py-2 text-left font-medium">Papel</th>
              <th className="px-3 py-2 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr key={member.id} className="border-t" style={{ borderColor: 'var(--color-border)' }}>
                <td className="px-3 py-2" style={{ color: 'var(--color-text)' }}>
                  {member.username}
                </td>
                <td className="px-3 py-2" style={{ color: 'var(--color-text-muted)' }}>
                  {member.user_id}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge
                    label={member.role === 'coordenador' ? 'Coordenador' : 'Colaborador'}
                    tone={member.role === 'coordenador' ? 'success' : 'neutral'}
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleRemove(member.id)}
                    className="text-xs"
                    style={{ color: '#b91c1c' }}
                  >
                    remover
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
