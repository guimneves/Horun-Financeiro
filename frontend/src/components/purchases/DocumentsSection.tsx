import { useCallback, useEffect, useRef, useState } from 'react'
import { purchasesApi } from '../../api/purchases'
import type { PurchaseDocument } from '../../types/purchase'
import { DOC_TYPE_LABELS } from '../../types/purchase'
import { FilePreviewModal, previewKind } from '../common/FilePreviewModal'

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
  const [notice, setNotice] = useState<string | null>(null)
  const [uploadingType, setUploadingType] = useState<string | null>(null)
  // documento aberto no leitor (sem baixar)
  const [viewing, setViewing] = useState<PurchaseDocument | null>(null)
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
    setNotice(null)
    try {
      const sent = await purchasesApi.uploadDocument(projectId, processId, docType, file)
      if (sent.warning) setNotice(sent.warning)
      load()
      // a cópia para a pasta do drive é feita logo depois do envio
      if (sent.drive_copy_status === 'pendente') window.setTimeout(load, 4000)
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
      {notice && (
        <p className="mb-2 rounded-md px-3 py-2 text-sm" style={{ background: '#fef9c3', color: '#854d0e' }}>
          {notice}
        </p>
      )}
      {shownTypes.map((docType) => {
        const items = byType.get(docType) ?? []
        const isQuote = docType === 'cotacao'
        const atQuoteLimit = isQuote && items.length >= 3
        const canUploadThisType = UPLOADABLE_TYPES.includes(docType)
        return (
          <div key={docType} className="mb-4">
            <div className="mb-1 flex flex-wrap items-center justify-between gap-x-2">
              <span className="text-sm font-medium" style={{ color: 'var(--color-text)' }}>
                {DOC_TYPE_LABELS[docType] ?? docType}
                {isQuote && <span style={{ color: 'var(--color-text-muted)' }}> ({items.length}/3)</span>}
              </span>
              {canUpload && canUploadThisType && !atQuoteLimit && (
                <label className="inline-flex min-h-10 cursor-pointer items-center text-xs font-medium md:min-h-0" style={{ color: 'var(--color-primary)' }}>
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
                  <li key={doc.id} className="flex flex-col gap-1 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-2">
                    <span className="min-w-0 truncate">
                      {previewKind(doc.original_filename) ? (
                        <button
                          type="button"
                          className="text-left"
                          onClick={() => setViewing(doc)}
                          style={{ color: 'var(--color-primary)' }}
                          title={`${doc.original_filename} — abrir para ler, sem baixar`}
                        >
                          {doc.original_filename}
                        </button>
                      ) : (
                        <a
                          href={purchasesApi.downloadUrl(projectId, processId, doc.id)}
                          style={{ color: 'var(--color-primary)' }}
                          title={doc.original_filename}
                        >
                          {doc.original_filename}
                        </a>
                      )}
                      {doc.storage_kind === 'drive' && (
                        <span className="ml-1 text-xs" style={{ color: 'var(--color-text-muted)' }} title="Arquivo no drive do projeto">
                          · drive
                        </span>
                      )}
                      <DriveCopyBadge doc={doc} />
                    </span>
                    <span className="flex items-center gap-2 sm:shrink-0">
                      <a
                        href={purchasesApi.downloadUrl(projectId, processId, doc.id)}
                        className="inline-flex min-h-10 items-center text-xs md:min-h-0"
                        style={{ color: 'var(--color-text-muted)' }}
                        title="Baixar"
                      >
                        baixar
                      </a>
                      <select
                        aria-label="Tipo do documento"
                        className="min-w-0 flex-1 rounded border px-1 py-0.5 text-xs sm:flex-none"
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
                          title={
                            doc.storage_kind === 'drive' || doc.drive_copy_status === 'copiado'
                              ? 'O arquivo continua na pasta do drive (o programa nunca apaga nada lá)'
                              : undefined
                          }
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
      {viewing && (
        <FilePreviewModal
          filename={viewing.original_filename}
          downloadUrl={purchasesApi.downloadUrl(projectId, processId, viewing.id)}
          kind={previewKind(viewing.original_filename)!}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  )
}

/** Se o arquivo está na pasta do processo no drive. Os do tipo "drive" já
 * estão lá; os anexados são copiados (quando a escrita no drive está ligada). */
function DriveCopyBadge({ doc }: { doc: PurchaseDocument }) {
  const inFolder = doc.storage_kind === 'drive' || doc.drive_copy_status === 'copiado'
  if (inFolder) {
    return (
      <span className="ml-1 text-xs" style={{ color: '#166534' }} title={doc.drive_copy_path ?? 'Na pasta do processo no drive'}>
        · na pasta ✓
      </span>
    )
  }
  if (doc.drive_copy_status === 'pendente') {
    return (
      <span className="ml-1 text-xs" style={{ color: 'var(--color-text-muted)' }} title={doc.drive_copy_error ?? undefined}>
        · aguardando o leitor de pastas
      </span>
    )
  }
  if (doc.drive_copy_status === 'erro') {
    return (
      <span
        className="ml-1 block whitespace-normal text-xs sm:inline"
        style={{ color: '#b91c1c' }}
        title={doc.drive_copy_error ?? undefined}
      >
        · não copiado: {doc.drive_copy_error ?? 'erro desconhecido'}
      </span>
    )
  }
  return null
}
