import { UNDER_CORE } from '../../lib/underCore'

/** "← Voltar ao Horun": link comum (carregamento completo da página, fora do
 * React Router) para a raiz do Core — mesma solução do RE7S
 * (Horun RE7S/frontend/src/components/Header.tsx). Só aparece sob o Core. */
export function BackToHorunLink({ className = '' }: { className?: string }) {
  if (!UNDER_CORE) return null
  return (
    <a href="/" className={`whitespace-nowrap text-sm ${className}`} style={{ color: 'var(--color-text-muted)' }}>
      ← Voltar ao Horun
    </a>
  )
}
