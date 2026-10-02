import nqtrLogo from './assets/nqtr-logo.png'

interface HorunFooterProps {
  /** Nome público do módulo, ex. "Horun · RE7S". */
  moduleName: string
  /** Autoria — mesmo padrão em todos os módulos (seção 9 do Prompt_refinado.md do RE7S). */
  author?: string
}

// Rodapé persistente padrão — mesmo em todo módulo, pra identidade visual
// consistente da plataforma (Prompt_Horun_Core.md, seção 2). Codinomes
// internos NUNCA aparecem aqui nem em qualquer outra tela (ver a regra no
// Prompt_Horun_Core.md, seção 2).
export function HorunFooter({ moduleName, author = 'Guilherme M. Neves' }: HorunFooterProps) {
  return (
    <footer
      className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-xs
                 border-[var(--color-border)] bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)]"
    >
      <div className="flex items-center gap-2">
        <img src={nqtrLogo} alt="NQTR · IQ-UFRJ" className="h-6 w-auto" />
        <span>NQTR, IQ-UFRJ</span>
      </div>
      <div>
        {moduleName} — um projeto <strong>Horun</strong> — {author}
      </div>
    </footer>
  )
}
