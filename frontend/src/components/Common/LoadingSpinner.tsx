import React from 'react'
import './Common.css'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  message?: string
  className?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  message,
  className = '',
}) => {
  return (
    <div
      className={`loading-spinner-wrapper ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className={`loading-spinner loading-spinner--${size}`} />
      {message && <p className="loading-spinner-text">{message}</p>}
    </div>
  )
}

export default LoadingSpinner
