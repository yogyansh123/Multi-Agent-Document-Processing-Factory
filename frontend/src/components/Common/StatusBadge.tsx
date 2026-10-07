import React from 'react'
import './Common.css'

interface StatusBadgeProps {
  status: string
  className?: string
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const norm = (status || '').toLowerCase()

  let styleVariant = 'uploaded'
  if (norm.includes('progress') || norm.includes('ing')) {
    styleVariant = 'processing'
  } else if (norm === 'approved' || norm === 'auto_approved' || norm === 'completed') {
    styleVariant = 'approved'
  } else if (norm === 'review_required' || norm === 'in_review') {
    styleVariant = 'review_required'
  } else if (norm.includes('failed') || norm === 'rejected') {
    styleVariant = 'rejected'
  }

  // Format label
  const label = status ? status.replace(/_/g, ' ') : 'UNKNOWN'

  return (
    <span
      className={`status-badge status-badge--${styleVariant} ${className}`}
      title={`Document Status: ${label}`}
      role="status"
    >
      <span className="status-badge--dot" aria-hidden="true" />
      {label}
    </span>
  )
}

export default StatusBadge
