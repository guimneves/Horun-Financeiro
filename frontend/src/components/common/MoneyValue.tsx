const formatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

interface MoneyValueProps {
  value: string | number
  /** Colore verde/vermelho pelo sinal — usado pra saldo, nunca pra valores neutros (planejado, realizado). */
  signColored?: boolean
}

export function MoneyValue({ value, signColored = false }: MoneyValueProps) {
  const numeric = typeof value === 'string' ? Number(value) : value
  const formatted = formatter.format(numeric)

  if (!signColored) return <span>{formatted}</span>

  const color = numeric < 0 ? '#dc2626' : 'var(--color-primary)'
  return <span style={{ color, fontWeight: 600 }}>{formatted}</span>
}
