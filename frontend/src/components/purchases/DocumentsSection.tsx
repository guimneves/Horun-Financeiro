import { useCallback, useEffect, useRef, useState } from 'react'
import { purchasesApi } from '../../api/purchases'
import type { PurchaseDocument } from '../../types/purchase'
import { DOC_TYPE_LABELS } from '../../types/purchase'

const UPLOADABLE_TYPES = ['cotacao', 'solicitacao_autorizacao', 'nota_fiscal', 'comprovante_recebimento', 'outro']

interface DocumentsSectionProps {
  projectId: number
  processId: number
  canDelete: boolean
  canUpload: boolean
  /** Notifica o pai (ex.: pra habilitar um botão de ação que exige documento) */
  onChange?: () => void
}

export function DocumentsSection({ projectId, processId, canDelete, canUpload, onChange }: DocumentsSectionProps) {
  const [docs, setDocs] = useState<PurchaseDocument[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploadingType, setUploadingType] = useState<string | null>(null)
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({})

  const load = useCallback(() => {
    purchasesApi
      .documents(projectId, processId)
      .then(setDocs)
      .catch((err) => setError(err.message))
  }, [projectId, processId])

  useEffect(() => {
    load()
  }, [load])

  async function handleUpload(docType: string, file: File) {
    setUploadingType(docType)
    setError(null)
    try {
      await purchasesApi.uploadDocument(projectId, processId, docType, file)
      load()
      onChange?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao enviar arquivo.')
    } finally {
      setUploadingType(null)
    }
  }

  async function handleDelete(docId: number) {
    setError(null)
    try {
      await purchasesApi.deleteDocument(projectId, processId, docId)
      load()
      onChange?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao remover documento.')
    }
  }

  async function handleReclassify(docId: number, docType: string) {
    setError(null)
    try {
      await purchasesApi.reclassifyDocument(projectId, processId, docId, docType)
      load()
      onChange?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao mudar o tipo do documento.')
    }
  }

  if (docs === null) return <p style={{ color: 'var(--color-text-muted)' }}>Carregando documentos…</p>

  const byType = new Map<string, PurchaseDocument[]>()
  for (const doc of docs) {
    byType.set(doc.doc_type, [...(byType.get(doc.doc_type) ?? []), doc])
  }
  // Os tipos que aceitam envio sempre aparecem; os demais (AF, boleto, pedido de
  // importação...) aparecem só quando há documento — vêm, em geral, do drive.
  const shownTypes = [...UPLOADABLE_TYPES, ...[...byType.keys()].filter((t) => !UPLOADABLE_TYPES.includes(t))]

  return (
    <div>
      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
      {shownTypes.map((docType) => {
        const items = byType.get(docType) ?? []
        const isQuote = docType === 'cotacao'
        const atQuoteLimit = isQuote && items.length >= 3
        const canUploadThisType = UPLOADABLE_TYPES.includes(docType)
        return (
          <div key={docType} className="mb-4">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                {DOC_TYPE_LABELS[docType] ?? docType}
                {isQuote && <span style={{ color: 'var(--color-text-muted)' }}> ({items.length}/3)</span>}
              </span>
              {canUpload && canUploadThisType && !atQuoteLimit && (
                <label className="cursor-pointer text-xs font-medium" style={{ color: 'var(--color-primary)' }}>
                  {uploadingType === docType ? 'Enviando…' : '+ Anexar arquivo'}
                  <input
                    ref={(el) => {
                      fileInputs.current[docType] = el
                    }}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) handleUpload(docType, file)
                      e.target.value = ''
                    }}
                  />
                </label>
              )}
            </div>
            {items.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Nenhum arquivo anexado.
              </p>
            ) : (
              <ul className="space-y-1">
                {items.map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between gap-2 text-sm">
                    <span className="min-w-0 truncate">
                      <a
                        href={purchasesApi.downloadUrl(projectId, processId, doc.id)}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: 'var(--color-primary)' }}
                        title={doc.original_filename}
                      >
                        {doc.original_filename}
                      </a>
                      {doc.storage_kind === 'drive' && (
                        <span className="ml-1 text-xs" style={{ color: 'var(--color-text-muted)' }} title="Arquivo no drive do projeto">
                          · drive
                        </span>
                      )}
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <select
                        aria-label="Tipo do documento"
                        className="rounded border px-1 py-0.5 text-xs"
                        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text-muted)' }}
                        value={doc.doc_type}
                        onChange={(e) => handleReclassify(doc.id, e.target.value)}
                      >
                        {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>
                            {label}
                          </option>
                        ))}
                      </select>
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => handleDelete(doc.id)}
                          className="text-xs"
                          style={{ color: '#b91c1c' }}
                          title={doc.storage_kind === 'drive' ? 'Só desfaz o vínculo; o arquivo do drive não é apagado' : undefined}
                        >
                          {doc.storage_kind === 'drive' ? 'desvincular' : 'remover'}
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}
