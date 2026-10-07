import React from 'react'
import './Common.css'

interface ErrorBannerProps {
  title?: string
  message: string
  onRetry?: () => void
  className?: string
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  title = 'An error occurred',
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div className={`error-banner ${className}`} role="alert">
      <div className="error-banner__icon" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <div className="error-banner__content">
        <div className="error-banner__title">{title}</div>
        <div className="error-banner__message">{message}</div>
      </div>
      {onRetry && (
        <button
          className="error-banner__retry-btn"
          onClick={onRetry}
          type="button"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export default ErrorBanner
