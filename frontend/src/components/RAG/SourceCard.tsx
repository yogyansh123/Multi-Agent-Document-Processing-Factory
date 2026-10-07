import React from 'react'
import type { RagSourceCitation } from './types'

interface SourceCardProps {
  source: RagSourceCitation
  isHighlighted?: boolean
  onClick?: () => void
}

export const SourceCard: React.FC<SourceCardProps> = ({
  source,
  isHighlighted = false,
  onClick,
}) => {
  const similarityPercent = Math.round(source.similarity_score * 100)

  return (
    <div
      className={`rag-source-card ${isHighlighted ? 'rag-source-card--highlighted' : ''}`}
      onClick={onClick}
      id={`source-card-${source.source_number}`}
      title="Click to focus on source and view document details"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      }}
    >
      <div className="rag-source-card__header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
          <span className="rag-source-tag">Source {source.source_number}</span>
          <span className="rag-source-filename" title={source.filename}>
            {source.filename}
          </span>
        </div>
        <span className="rag-source-score" title="Cosine Similarity Score">
          {similarityPercent}% match
        </span>
      </div>

      <div className="rag-source-excerpt">
        "{source.excerpt}"
      </div>

      <div className="rag-source-card__footer">
        <span>
          Page {source.page_number !== null && source.page_number !== undefined ? source.page_number : '1'}
          {source.document_type ? ` • ${source.document_type}` : ''}
        </span>
        <span style={{ fontFamily: 'monospace', fontSize: '10px' }}>
          Doc ID: {source.document_id.slice(0, 8)}...
        </span>
      </div>
    </div>
  )
}

export default SourceCard
