const formatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

interface MoneyValueProps {
  value: string | number | null
  /** Colore verde/vermelho pelo sinal — usado pra saldo, nunca pra valores neutros (planejado, realizado). */
  signColored?: boolean
}

export function MoneyValue({ value, signColored = false }: MoneyValueProps) {
  if (value === null) {
    // Backend não revelou o valor pra este usuário (ver core/redaction.py) — nunca "R$ 0,00" no lugar de nada.
    return <span style={{ color: 'var(--color-text-muted)' }}>—</span>
  }
  const numeric = typeof value === 'string' ? Number(value) : value
  const formatted = formatter.format(numeric)

  if (!signColored) return <span>{formatted}</span>

  const color = numeric < 0 ? '#dc2626' : 'var(--color-primary)'
  return <span style={{ color, fontWeight: 600 }}>{formatted}</span>
}
