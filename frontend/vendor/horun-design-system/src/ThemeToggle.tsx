import { motion } from 'framer-motion'
import { useTheme, type ThemeMode } from './ThemeProvider'

const LABELS: Record<ThemeMode, string> = {
  light: 'Claro',
  dim: 'Semi-escuro',
  dark: 'Escuro',
}

const ICONS: Record<ThemeMode, string> = {
  light: '☀️',
  dim: '🌗',
  dark: '🌙',
}

export function ThemeToggle() {
  const { theme, cycleTheme } = useTheme()

  return (
    <motion.button
      type="button"
      onClick={cycleTheme}
      whileTap={{ scale: 0.92 }}
      className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm
                 border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]
                 hover:bg-[var(--color-bg-elevated)] transition-colors"
      title={`Tema: ${LABELS[theme]} (clique para trocar)`}
      aria-label="Alternar tema"
    >
      <span aria-hidden>{ICONS[theme]}</span>
      <span className="hidden sm:inline">{LABELS[theme]}</span>
    </motion.button>
  )
}
