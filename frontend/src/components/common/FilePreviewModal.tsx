import { useEffect } from 'react'

export type PreviewKind = 'pdf' | 'image' | 'text'

const KIND_BY_EXTENSION: Record<string, PreviewKind> = {
  pdf: 'pdf',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  gif: 'image',
  webp: 'image',
  txt: 'text',
}

/** O que dá para ler na página sem baixar — a mesma lista fechada do
 * backend (`PREVIEWABLE_TYPES` em core/files.py). Nulo = só download. */
export function previewKind(filename: string): PreviewKind | null {
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  return KIND_BY_EXTENSION[ext] ?? null
}

/** Mesma URL de download, pedindo para exibir em vez de baixar. */
export function inlineUrl(downloadUrl: string): string {
  return downloadUrl + (downloadUrl.includes('?') ? '&' : '?') + 'inline=true'
}

/** Leitor de arquivo sobre a página (pedido do usuário: ler os PDFs sem
 * baixar) — usa o leitor de PDF do próprio navegador. */
export function FilePreviewModal({
  filename,
  downloadUrl,
  kind,
  onClose,
}: {
  filename: string
  downloadUrl: string
  kind: PreviewKind
  onClose: () => void
}) {
  const url = inlineUrl(downloadUrl)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4"
      style={{ background: 'rgba(0, 0, 0, 0.55)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Visualizar ${filename}`}
    >
      <div
        className="flex h-full w-full max-w-5xl flex-col overflow-hidden border sm:rounded-lg"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b px-3 py-2 sm:px-4" style={{ borderColor: 'var(--color-border)' }}>
          <span className="min-w-0 truncate text-sm font-medium" style={{ color: 'var(--color-text)' }} title={filename}>
            {filename}
          </span>
          <span className="flex shrink-0 items-center gap-3 text-sm">
            <a href={url} target="_blank" rel="noreferrer" style={{ color: 'var(--color-primary)' }}>
              Abrir em nova aba
            </a>
            <a href={downloadUrl} style={{ color: 'var(--color-primary)' }}>
              Baixar
            </a>
            <button type="button" onClick={onClose} aria-label="Fechar" className="px-2" style={{ color: 'var(--color-text-muted)' }}>
              ✕
            </button>
          </span>
        </div>
        <div className="min-h-0 flex-1" style={{ background: 'var(--color-surface)' }}>
          {kind === 'image' ? (
            <div className="flex h-full items-center justify-center overflow-auto p-2">
              <img src={url} alt={filename} className="max-h-full max-w-full object-contain" />
            </div>
          ) : (
            <iframe src={url} title={filename} className="h-full w-full border-0" />
          )}
        </div>
      </div>
    </div>
  )
}
