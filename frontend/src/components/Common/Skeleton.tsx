import React from 'react'
import './Common.css'

interface SkeletonProps {
  width?: string | number
  height?: string | number
  borderRadius?: string | number
  className?: string
  count?: number
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '20px',
  borderRadius = 'var(--radius-sm)',
  className = '',
  count = 1,
}) => {
  const elements = Array.from({ length: count }, (_, idx) => (
    <div
      key={idx}
      className={`skeleton-box ${className}`}
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
        borderRadius: typeof borderRadius === 'number' ? `${borderRadius}px` : borderRadius,
        marginBottom: count > 1 && idx < count - 1 ? '8px' : undefined,
      }}
      aria-hidden="true"
    />
  ))

  return <>{elements}</>
}

export default Skeleton
