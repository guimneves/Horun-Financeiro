import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../api/auth'
import { projectsApi } from '../api/projects'
import { useProjects } from '../context/ProjectsContext'
import { StatusBadge } from '../components/common/StatusBadge'

const field = { borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }

/** Criar projeto — só o admin do Core pode (a rota confere); quem cria já
 * entra como coordenador dele. */
function NewProjectForm({ onCreated, onCancel }: { onCreated: (id: number) => void; onCancel: () => void }) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [fundingAgency, setFundingAgency] = useState('Petrobras')
  const [foundation, setFoundation] = useState('COPPETEC/UFRJ')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleCreate() {
    if (!code.trim() || !name.trim()) return
    setSaving(true)
    setError(null)
    try {
      const project = await projectsApi.create({
        code: code.trim(),
        name: name.trim(),
        funding_agency: fundingAgency.trim(),
        foundation: foundation.trim(),
        start_date: startDate || null,
        end_date: endDate || null,
      })
      onCreated(project.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar o projeto.')
    } finally {
      setSaving(false)
    }
  }

  const inputs: [string, string, (v: string) => void, string, string?][] = [
    ['Código (nº COPPETEC)', code, setCode, 'ex.: 25.465'],
    ['Nome', name, setName, 'ex.: Maturação Artificial'],
    ['Financiadora', fundingAgency, setFundingAgency, ''],
    ['Fundação', foundation, setFoundation, ''],
    ['Início', startDate, setStartDate, '', 'date'],
    ['Fim', endDate, setEndDate, '', 'date'],
  ]

  return (
    <div className="mb-4 rounded-lg border p-4" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {inputs.map(([label, value, setter, placeholder, type]) => (
          <div key={label}>
            <label className="mb-1 block text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {label}
            </label>
            <input
              type={type ?? 'text'}
              className="w-full rounded-md border px-3 py-1.5 text-sm"
              style={field}
              placeholder={placeholder}
              value={value}
              onChange={(e) => setter(e.target.value)}
            />
          </div>
        ))}
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={handleCreate}
          disabled={saving || !code.trim() || !name.trim()}
          className="rounded-md px-4 py-1.5 text-sm font-medium disabled:opacity-50"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          {saving ? 'Criando…' : 'Criar projeto'}
        </button>
        <button type="button" onClick={onCancel} style={{ color: 'var(--color-text-muted)' }}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

export function ProjectListPage() {
  const { projects, error, reload } = useProjects()
  const navigate = useNavigate()
  const [isCoreAdmin, setIsCoreAdmin] = useState(false)
  const [showNew, setShowNew] = useState(false)

  useEffect(() => {
    authApi
      .me()
      .then((me) => setIsCoreAdmin(me.is_core_admin))
      .catch(() => setIsCoreAdmin(false)) // sem identidade: só não mostra o botão (a lista já mostra o erro)
  }, [])

  if (error) return <p className="p-6 text-red-600">Erro ao carregar projetos: {error}</p>
  if (projects === null) return <p className="p-6">Carregando…</p>

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold" style={{ color: 'var(--color-text)' }}>
          Projetos
        </h2>
        {isCoreAdmin && !showNew && (
          <button
            type="button"
            onClick={() => setShowNew(true)}
            className="rounded-md px-4 py-2 text-sm font-medium"
            style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
          >
            + Novo projeto
          </button>
        )}
      </div>

      {showNew && (
        <NewProjectForm
          onCancel={() => setShowNew(false)}
          onCreated={(id) => {
            setShowNew(false)
            reload()
            navigate(`/projects/${id}`)
          }}
        />
      )}

      {projects.length === 0 && !showNew && (
        <p style={{ color: 'var(--color-text-muted)' }}>
          {isCoreAdmin
            ? 'Nenhum projeto ainda — crie o primeiro em "+ Novo projeto".'
            : 'Você ainda não tem acesso a nenhum projeto.'}
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Link
            key={project.id}
            to={`/projects/${project.id}`}
            className="block rounded-lg border p-4 transition-colors hover:opacity-90"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Processo {project.code}
              </span>
              <StatusBadge label={project.my_role ?? ''} tone={project.my_role === 'coordenador' ? 'success' : 'neutral'} />
            </div>
            <div className="font-medium" style={{ color: 'var(--color-text)' }}>
              {project.name}
            </div>
            <div className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
              {project.funding_agency} · {project.foundation}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
