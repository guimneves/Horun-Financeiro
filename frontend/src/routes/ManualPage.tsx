import { useLayoutEffect, useRef, useState } from 'react'
import { MANUAL_INTRO, MANUAL_SECTIONS, MANUAL_TITLE } from '../manual/content'

const muted = { color: 'var(--color-text-muted)' }

const normalize = (text: string) =>
  text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()

/** Aba Manual (Prompt_Horun_Modulo.md, seção 12): índice com âncoras, busca
 * simples por texto e "Imprimir / salvar PDF" pelo próprio navegador. O
 * conteúdo fica em manual/content.tsx. */
export function ManualPage() {
  const [query, setQuery] = useState('')
  // texto de cada seção, lido do que foi desenhado — a busca acha o que a
  // pessoa vê, sem manter uma cópia do texto em outro lugar
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({})
  const [texts, setTexts] = useState<Record<string, string>>({})

  useLayoutEffect(() => {
    const next: Record<string, string> = {}
    for (const section of MANUAL_SECTIONS) {
      next[section.id] = normalize(sectionRefs.current[section.id]?.textContent ?? section.title)
    }
    setTexts(next)
  }, [])

  const terms = normalize(query).split(/\s+/).filter(Boolean)
  const matches = (id: string) => terms.every((t) => (texts[id] ?? '').includes(t))
  const visible = MANUAL_SECTIONS.filter((s) => matches(s.id))

  return (
    <div className="mx-auto max-w-3xl p-4 md:p-6 print:max-w-none print:p-0">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-xl font-semibold md:text-2xl" style={{ color: 'var(--color-text)' }}>
          {MANUAL_TITLE}
        </h1>
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded-md px-4 py-2 text-sm font-medium print:hidden"
          style={{ background: 'var(--color-primary)', color: 'var(--color-primary-contrast)' }}
        >
          Imprimir / salvar PDF
        </button>
      </div>

      <div className="mb-4 text-sm leading-relaxed" style={{ color: 'var(--color-text)' }}>
        {MANUAL_INTRO}
      </div>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Buscar no manual (ex.: nota fiscal, cotação, saldo)"
        aria-label="Buscar no manual"
        className="mb-4 w-full rounded-md border px-3 py-2 text-sm print:hidden"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)' }}
      />

      <nav
        aria-label="Índice do manual"
        className="mb-6 rounded-lg border p-4 print:hidden"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-elevated)' }}
      >
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide" style={muted}>
          Índice
        </div>
        {visible.length === 0 ? (
          <p className="text-sm" style={muted}>
            Nada encontrado para "{query}".
          </p>
        ) : (
          <ol className="grid grid-cols-1 gap-x-6 text-sm sm:grid-cols-2">
            {visible.map((section) => (
              <li key={section.id}>
                <a href={`#${section.id}`} className="inline-flex min-h-10 items-center md:min-h-0 md:py-0.5" style={{ color: 'var(--color-primary)' }}>
                  {section.title}
                </a>
              </li>
            ))}
          </ol>
        )}
      </nav>

      <div className="space-y-8">
        {MANUAL_SECTIONS.map((section) => (
          <section
            key={section.id}
            id={section.id}
            ref={(el) => {
              sectionRefs.current[section.id] = el
            }}
            hidden={!matches(section.id)}
            className="scroll-mt-4 break-inside-avoid-page"
          >
            <h2 className="mb-2 text-lg font-semibold" style={{ color: 'var(--color-text)' }}>
              {section.title}
            </h2>
            <div className="space-y-2 text-sm leading-relaxed" style={{ color: 'var(--color-text)' }}>
              {section.body}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
