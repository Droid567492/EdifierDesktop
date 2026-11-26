import type { ReactNode } from 'react'
import { X } from 'lucide-react'

interface AlertBannerProps {
  alertId: string
  variant?: 'info' | 'warning' | 'error' | 'update'
  icon?: ReactNode
  title?: string
  message: ReactNode
  actions?: ReactNode
  onDismiss?: () => void
  onDontShowAgain: (alertId: string) => void
}

export function AlertBanner({
  alertId,
  variant = 'warning',
  icon,
  title,
  message,
  actions,
  onDismiss,
  onDontShowAgain,
}: AlertBannerProps) {
  const variantClass =
    variant === 'error'
      ? 'error'
      : variant === 'update'
        ? 'update'
        : variant === 'info'
          ? 'info'
          : ''

  return (
    <div className={`notice-banner ${variantClass}`} role="alert">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, minWidth: 0, flex: '1 1 240px' }}>
        {icon && <span style={{ marginTop: 2, flexShrink: 0 }}>{icon}</span>}
        <div style={{ minWidth: 0 }}>
          {title && <div style={{ fontWeight: 700, marginBottom: 2 }}>{title}</div>}
          <div>{message}</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        {actions}
        <button
          className="btn"
          style={{ padding: '4px 9px', fontSize: 11.5 }}
          onClick={() => onDontShowAgain(alertId)}
          title="Hide this alert permanently"
        >
          Don&apos;t show again
        </button>
        {onDismiss && (
          <button
            className="btn btn-icon"
            style={{ padding: '4px 6px' }}
            onClick={onDismiss}
            aria-label="Dismiss alert"
            title="Dismiss"
          >
            <X size={13} />
          </button>
        )}
      </div>
    </div>
  )
}
