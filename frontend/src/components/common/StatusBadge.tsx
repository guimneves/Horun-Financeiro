interface StatusBadgeProps {
  label: string
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
}

const TONE_STYLES: Record<NonNullable<StatusBadgeProps['tone']>, { bg: string; fg: string }> = {
  neutral: { bg: 'var(--color-surface)', fg: 'var(--color-text-muted)' },
  success: { bg: '#dcfce7', fg: '#15803d' },
  warning: { bg: '#fef9c3', fg: '#a16207' },
  danger: { bg: '#fee2e2', fg: '#b91c1c' },
}

export function StatusBadge({ label, tone = 'neutral' }: StatusBadgeProps) {
  const { bg, fg } = TONE_STYLES[tone]
  return (
    <span
      className="rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ background: bg, color: fg }}
    >
      {label}
    </span>
  )
}
