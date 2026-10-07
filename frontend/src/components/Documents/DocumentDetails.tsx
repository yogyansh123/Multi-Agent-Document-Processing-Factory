import React, { useState, useEffect, useCallback } from 'react'
import { documentsApi, ragApi, formatApiError } from '../../api/client'
import type { DocumentWithHistoryResponse } from '../../types'
import {
  ConfirmModal,
  ErrorBanner,
  LoadingSpinner,
  StatusBadge,
} from '../Common'
import ProcessingPipeline from './ProcessingPipeline'
import './Documents.css'

interface DocumentDetailsProps {
  documentId: string
  onBack: () => void
  onNavigateToReview?: (documentId: string) => void
}

export const DocumentDetails: React.FC<DocumentDetailsProps> = ({
  documentId,
  onBack,
  onNavigateToReview,
}) => {
  const [doc, setDoc] = useState<DocumentWithHistoryResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Actions state
  const [isProcessing, setIsProcessing] = useState(false)
  const [isIndexing, setIsIndexing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [ocrExpanded, setOcrExpanded] = useState(false)

  const fetchDocument = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await documentsApi.get(documentId)
      setDoc(data)
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    fetchDocument()
  }, [fetchDocument])

  const handleStartProcessing = async () => {
    setIsProcessing(true)
    setError(null)
    try {
      await documentsApi.process(documentId)
      await fetchDocument()
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsProcessing(false)
    }
  }

  const handleManualIndex = async () => {
    setIsIndexing(true)
    setError(null)
    try {
      await ragApi.indexDocument(documentId)
      await fetchDocument()
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsIndexing(false)
    }
  }

  const handleDeleteConfirm = async () => {
    setIsDeleting(true)
    setError(null)
    try {
      await documentsApi.delete(documentId)
      setShowDeleteModal(false)
      onBack()
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsDeleting(false)
    }
  }

  const formatDate = (isoString?: string | null): string => {
    if (!isoString) return '—'
    try {
      return new Date(isoString).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  if (isLoading && !doc) {
    return (
      <div className="doc-page">
        <LoadingSpinner size="lg" message="Loading document details..." />
      </div>
    )
  }

  if (error && !doc) {
    return (
      <div className="doc-page">
        <ErrorBanner message={error} onRetry={fetchDocument} />
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          Back to Documents
        </button>
      </div>
    )
  }

  if (!doc) return null

  const canProcess = doc.status === 'UPLOADED' || doc.status === 'FAILED'
  const isReviewRequired = doc.status === 'REVIEW_REQUIRED' || doc.status === 'IN_REVIEW'
  const overallConf = doc.overall_confidence

  return (
    <div className="doc-page">
      {/* Top Header & Actions */}
      <div className="doc-header">
        <div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onBack}
            style={{ marginBottom: '8px', padding: '4px 10px', fontSize: '0.75rem' }}
          >
            ← Back to Documents
          </button>
          <h1 className="doc-header__title">
            <span>{doc.original_filename}</span>
            <StatusBadge status={doc.status} />
          </h1>
          <p className="doc-header__subtitle">
            ID: <span style={{ fontFamily: 'monospace' }}>{doc.id}</span> · Uploaded on {formatDate(doc.created_at)}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {canProcess && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleStartProcessing}
              disabled={isProcessing}
            >
              {isProcessing ? 'Starting...' : 'Process Document'}
            </button>
          )}

          {isReviewRequired && onNavigateToReview && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => onNavigateToReview(doc.id)}
              style={{ background: 'var(--color-accent-secondary)' }}
            >
              Open in Review Queue
            </button>
          )}

          {doc.status === 'APPROVED' && !doc.rag_indexed && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleManualIndex}
              disabled={isIndexing}
            >
              {isIndexing ? 'Indexing...' : 'Index in Vector DB'}
            </button>
          )}

          <button
            type="button"
            className="btn btn-danger"
            onClick={() => setShowDeleteModal(true)}
          >
            Delete
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

      {/* Visual Processing Pipeline */}
      <ProcessingPipeline
        documentId={doc.id}
        currentStatus={doc.status}
        ragIndexed={doc.rag_indexed}
        onStatusChange={() => fetchDocument()}
      />

      {/* Cockpit Grid */}
      <div className="doc-details-grid">
        {/* Left Column: Metadata & Confidence & RAG */}
        <div className="doc-col-4" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Metadata Card */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                Document Info
              </h2>
            </div>
            <dl className="meta-dl">
              <dt className="meta-dt">File Type</dt>
              <dd className="meta-dd">{doc.file_type.toUpperCase()}</dd>

              <dt className="meta-dt">MIME Type</dt>
              <dd className="meta-dd" style={{ fontSize: '0.8rem' }}>{doc.mime_type}</dd>

              <dt className="meta-dt">File Size</dt>
              <dd className="meta-dd">{(doc.file_size / 1024).toFixed(1)} KB</dd>

              <dt className="meta-dt">Doc Type</dt>
              <dd className="meta-dd">{doc.document_type || 'Unclassified'}</dd>

              <dt className="meta-dt">Status</dt>
              <dd className="meta-dd"><StatusBadge status={doc.status} /></dd>

              <dt className="meta-dt">Last Update</dt>
              <dd className="meta-dd" style={{ fontSize: '0.8rem' }}>{formatDate(doc.updated_at)}</dd>
            </dl>
          </div>

          {/* Confidence Score Card */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                Confidence Scoring
              </h2>
            </div>

            {overallConf !== null && overallConf !== undefined ? (
              <>
                <div className="confidence-box">
                  <span className="confidence-score-big">
                    {(overallConf * 100).toFixed(0)}%
                  </span>
                  {doc.confidence_recommendation && (
                    <span
                      className={`confidence-rec-pill ${
                        doc.confidence_recommendation === 'AUTO_APPROVE'
                          ? 'confidence-rec-pill--approve'
                          : 'confidence-rec-pill--review'
                      }`}
                    >
                      {doc.confidence_recommendation.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>

                <div className="factor-breakdown-list">
                  <div className="factor-row">
                    <span>Classification</span>
                    <div className="factor-bar">
                      <div
                        className="factor-bar-fill"
                        style={{ width: `${((doc.classification_confidence ?? 0) * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span>{doc.classification_confidence ? `${(doc.classification_confidence * 100).toFixed(0)}%` : '—'}</span>
                  </div>

                  <div className="factor-row">
                    <span>Extraction</span>
                    <div className="factor-bar">
                      <div
                        className="factor-bar-fill"
                        style={{ width: `${((doc.extraction_confidence ?? 0) * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span>{doc.extraction_confidence ? `${(doc.extraction_confidence * 100).toFixed(0)}%` : '—'}</span>
                  </div>

                  <div className="factor-row">
                    <span>Validation</span>
                    <div className="factor-bar">
                      <div
                        className="factor-bar-fill"
                        style={{ width: `${((doc.validation_confidence ?? 0) * 100).toFixed(0)}%` }}
                      />
                    </div>
                    <span>{doc.validation_confidence ? `${(doc.validation_confidence * 100).toFixed(0)}%` : '—'}</span>
                  </div>
                </div>
              </>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                Confidence will be calculated once validation is complete.
              </p>
            )}
          </div>

          {/* RAG Status Card */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                RAG Intelligence
              </h2>
            </div>
            <dl className="meta-dl">
              <dt className="meta-dt">Vector Indexed</dt>
              <dd className="meta-dd">
                {doc.rag_indexed ? (
                  <span style={{ color: 'var(--color-accent-tertiary)', fontWeight: 600 }}>YES</span>
                ) : (
                  <span style={{ color: 'var(--color-text-muted)' }}>NO</span>
                )}
              </dd>

              <dt className="meta-dt">Chunks</dt>
              <dd className="meta-dd">{doc.rag_chunk_count ?? '0'}</dd>

              <dt className="meta-dt">Model</dt>
              <dd className="meta-dd" style={{ fontSize: '0.8rem' }}>{doc.rag_embedding_model || '—'}</dd>

              <dt className="meta-dt">Indexed At</dt>
              <dd className="meta-dd" style={{ fontSize: '0.8rem' }}>{formatDate(doc.rag_indexed_at)}</dd>
            </dl>
          </div>
        </div>

        {/* Right Column: AI Extraction, Validation, Classification, OCR, History */}
        <div className="doc-col-8" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Classification Section */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
                Classification Analysis
              </h2>
              {doc.document_type && (
                <span className="status-badge status-badge--uploaded">
                  {doc.document_type}
                </span>
              )}
            </div>

            {doc.classification_reasoning ? (
              <div>
                <p style={{ fontSize: '0.875rem', color: 'var(--color-text-primary)', marginBottom: '12px' }}>
                  {doc.classification_reasoning}
                </p>
                {doc.classification_signals && doc.classification_signals.length > 0 && (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {doc.classification_signals.map((sig, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: '0.75rem',
                          background: 'rgba(79, 142, 247, 0.1)',
                          border: '1px solid rgba(79, 142, 247, 0.25)',
                          borderRadius: '4px',
                          padding: '2px 8px',
                          color: '#8bb6fd',
                        }}
                      >
                        #{sig}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                Classification pending.
              </p>
            )}
          </div>

          {/* Extracted Data Section */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <line x1="9" y1="3" x2="9" y2="21" />
                </svg>
                Structured Extracted Data
              </h2>
              {doc.extraction_version && (
                <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                  Schema: {doc.extraction_version}
                </span>
              )}
            </div>

            {doc.extracted_data && Object.keys(doc.extracted_data).length > 0 ? (
              <div className="structured-kv-grid">
                {Object.entries(doc.extracted_data).map(([key, val]) => {
                  if (typeof val === 'object' && val !== null) {
                    return (
                      <div key={key} className="structured-kv-card" style={{ gridColumn: 'span 2' }}>
                        <div className="structured-kv-label">{key.replace(/_/g, ' ')}</div>
                        <pre style={{ fontSize: '0.75rem', margin: '4px 0 0', overflowX: 'auto' }}>
                          {JSON.stringify(val, null, 2)}
                        </pre>
                      </div>
                    )
                  }
                  return (
                    <div key={key} className="structured-kv-card">
                      <div className="structured-kv-label">{key.replace(/_/g, ' ')}</div>
                      <div className="structured-kv-value">{String(val ?? '—')}</div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                Structured extraction has not completed yet.
              </p>
            )}
          </div>

          {/* Validation Section */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                Validation Rules Report
              </h2>
              {doc.validation_score !== null && doc.validation_score !== undefined && (
                <span
                  style={{
                    fontFamily: 'monospace',
                    fontWeight: 700,
                    fontSize: '0.875rem',
                    color: doc.validation_score >= 0.8 ? 'var(--color-accent-success)' : 'var(--color-accent-warning)',
                  }}
                >
                  Score: {(doc.validation_score * 100).toFixed(0)}%
                </span>
              )}
            </div>

            {doc.validation_result?.issues && doc.validation_result.issues.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {doc.validation_result.issues.map((iss, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      padding: '8px 12px',
                      background: 'rgba(13, 21, 40, 0.6)',
                      borderRadius: '6px',
                      borderLeft: `3px solid ${
                        iss.severity === 'ERROR'
                          ? 'var(--color-accent-danger)'
                          : iss.severity === 'WARNING'
                          ? 'var(--color-accent-warning)'
                          : 'var(--color-accent-primary)'
                      }`,
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background:
                          iss.severity === 'ERROR'
                            ? 'rgba(255, 77, 109, 0.2)'
                            : iss.severity === 'WARNING'
                            ? 'rgba(245, 166, 35, 0.2)'
                            : 'rgba(79, 142, 247, 0.2)',
                        color:
                          iss.severity === 'ERROR'
                            ? '#ff859d'
                            : iss.severity === 'WARNING'
                            ? '#fbc770'
                            : '#8bb6fd',
                      }}
                    >
                      {iss.severity}
                    </span>
                    <div style={{ flex: 1, fontSize: '0.8125rem' }}>
                      <div style={{ fontWeight: 600, color: '#fff' }}>
                        Field: <code>{iss.field}</code> — {iss.code}
                      </div>
                      <div style={{ color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                        {iss.message}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : doc.validation_result ? (
              <div style={{ color: 'var(--color-accent-success)', fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                All deterministic and semantic validation rules passed without issues.
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                Validation pending.
              </p>
            )}
          </div>

          {/* OCR Panel */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="4 7 4 4 20 4 20 7" />
                  <line x1="9" y1="20" x2="15" y2="20" />
                  <line x1="12" y1="4" x2="12" y2="20" />
                </svg>
                Extracted OCR Text
              </h2>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setOcrExpanded((prev) => !prev)}
                style={{ padding: '3px 10px', fontSize: '0.75rem' }}
              >
                {ocrExpanded ? 'Collapse' : 'Expand'}
              </button>
            </div>

            {doc.ocr_text ? (
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
                  Provider: {doc.ocr_provider || 'Direct'} · Pages: {doc.ocr_page_count ?? 1} · Processing Time: {doc.ocr_processing_time_ms ?? '—'} ms
                </div>
                <div
                  className="text-viewer-box"
                  style={{ maxHeight: ocrExpanded ? '500px' : '160px' }}
                >
                  {doc.ocr_text}
                </div>
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                OCR text not available yet.
              </p>
            )}
          </div>

          {/* Chronological Audit Timeline */}
          <div className="card-panel">
            <div className="card-panel__header">
              <h2 className="card-panel__title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                Audit Timeline & Processing History
              </h2>
            </div>

            {doc.processing_history && doc.processing_history.length > 0 ? (
              <div className="timeline">
                {doc.processing_history.map((h) => (
                  <div key={h.id} className="timeline-item">
                    <div
                      className={`timeline-dot ${
                        h.status === 'COMPLETED'
                          ? 'timeline-dot--completed'
                          : h.status === 'FAILED'
                          ? 'timeline-dot--failed'
                          : ''
                      }`}
                    />
                    <div className="timeline-header">
                      <span className="timeline-stage">{h.stage}</span>
                      <span className="timeline-time">{formatDate(h.started_at)}</span>
                    </div>
                    <div className="timeline-body">
                      Status: <strong>{h.status}</strong>
                      {h.duration_ms !== null && h.duration_ms !== undefined && (
                        <span> · Duration: {h.duration_ms}ms</span>
                      )}
                      {h.message && <p style={{ margin: '4px 0 0' }}>{h.message}</p>}
                      {h.error_details && (
                        <p style={{ margin: '4px 0 0', color: '#ff859d' }}>Error: {h.error_details}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', margin: 0 }}>
                No processing history recorded.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={showDeleteModal}
        title="Delete Document"
        message={`Are you sure you want to permanently delete "${doc.original_filename}"?`}
        confirmLabel="Delete"
        variant="danger"
        isLoading={isDeleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteModal(false)}
      />
    </div>
  )
}

export default DocumentDetails
