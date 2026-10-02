import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

// Três modos — não é um toggle binário (ver Prompt_Horun_Core.md, seção 2).
export type ThemeMode = 'light' | 'dim' | 'dark'

// Chave ÚNICA e compartilhada entre todos os módulos (não prefixada por
// módulo) — como tudo roda sob a mesma origem via o gateway do Core, trocar
// o tema num módulo já reflete nos outros.
const STORAGE_KEY = 'horun-theme'
const MODES: ThemeMode[] = ['light', 'dim', 'dark']

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

function readStoredTheme(): ThemeMode | null {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored && (MODES as string[]).includes(stored) ? (stored as ThemeMode) : null
}

interface ThemeContextValue {
  theme: ThemeMode
  setTheme: (mode: ThemeMode) => void
  cycleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(
    () => readStoredTheme() ?? (systemPrefersDark() ? 'dark' : 'light'),
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    window.localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      setTheme: setThemeState,
      cycleTheme: () =>
        setThemeState((current) => MODES[(MODES.indexOf(current) + 1) % MODES.length]),
    }),
    [theme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme precisa estar dentro de <ThemeProvider>')
  return ctx
}
