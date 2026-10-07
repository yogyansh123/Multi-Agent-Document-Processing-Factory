import React, { useState, useEffect, useCallback } from 'react'
import { documentsApi, formatApiError } from '../../api/client'
import type { DocumentResponse } from '../../types'
import {
  ConfirmModal,
  EmptyState,
  ErrorBanner,
  LoadingSpinner,
  StatusBadge,
} from '../Common'
import './Documents.css'

interface DocumentListProps {
  onSelectDocument: (documentId: string) => void
  onNavigateToUpload: () => void
}

export const DocumentList: React.FC<DocumentListProps> = ({
  onSelectDocument,
  onNavigateToUpload,
}) => {
  const [documents, setDocuments] = useState<DocumentResponse[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  const [page, setPage] = useState(1)
  const pageSize = 10

  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')

  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Actions
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)
  const [deleteTargetDoc, setDeleteTargetDoc] = useState<DocumentResponse | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await documentsApi.list({
        page,
        page_size: pageSize,
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        document_type: typeFilter || undefined,
      })
      setDocuments(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages || 1)
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsLoading(false)
    }
  }, [page, search, statusFilter, typeFilter])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchDocuments()
  }

  const handleProcessDocument = async (e: React.MouseEvent, doc: DocumentResponse) => {
    e.stopPropagation()
    setActionLoadingId(doc.id)
    setError(null)
    try {
      await documentsApi.process(doc.id)
      await fetchDocuments()
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTargetDoc) return
    setIsDeleting(true)
    setError(null)
    try {
      await documentsApi.delete(deleteTargetDoc.id)
      setDeleteTargetDoc(null)
      await fetchDocuments()
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsDeleting(false)
    }
  }

  const formatDate = (isoString: string): string => {
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

  return (
    <div className="doc-page">
      <div className="doc-header">
        <div>
          <h1 className="doc-header__title">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            Documents
          </h1>
          <p className="doc-header__subtitle">
            Manage, process, and track all incoming enterprise documents.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={onNavigateToUpload}
          id="btn-upload-new"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Upload Document
        </button>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchDocuments} />}

      {/* Filter and Search Bar */}
      <form className="doc-filter-bar" onSubmit={handleSearchSubmit}>
        <div className="doc-search-box">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="search"
            placeholder="Search by filename..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            id="doc-search-input"
          />
        </div>

        <select
          className="doc-select"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          aria-label="Filter by Status"
        >
          <option value="">All Statuses</option>
          <option value="UPLOADED">Uploaded</option>
          <option value="OCR_COMPLETED">OCR Completed</option>
          <option value="CLASSIFIED">Classified</option>
          <option value="EXTRACTED">Extracted</option>
          <option value="AUTO_APPROVED">Auto Approved</option>
          <option value="REVIEW_REQUIRED">Review Required</option>
          <option value="IN_REVIEW">In Review</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="FAILED">Failed</option>
        </select>

        <select
          className="doc-select"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value)
            setPage(1)
          }}
          aria-label="Filter by Document Type"
        >
          <option value="">All Types</option>
          <option value="INVOICE">Invoice</option>
          <option value="RECEIPT">Receipt</option>
          <option value="PURCHASE_ORDER">Purchase Order</option>
          <option value="CONTRACT">Contract</option>
          <option value="OTHER">Other</option>
        </select>

        <button type="submit" className="btn btn-secondary">
          Filter
        </button>
      </form>

      {/* Table Content */}
      <div className="doc-table-card">
        {isLoading ? (
          <LoadingSpinner message="Loading documents..." />
        ) : documents.length === 0 ? (
          <EmptyState
            title="No documents found"
            description={
              search || statusFilter || typeFilter
                ? 'Try adjusting your search filters.'
                : 'Upload your first document to start the multi-agent processing pipeline.'
            }
            action={{
              label: 'Upload Document',
              onClick: onNavigateToUpload,
            }}
          />
        ) : (
          <>
            <table className="doc-table" id="documents-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Confidence</th>
                  <th>Uploaded</th>
                  <th>RAG</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => {
                  const canProcess =
                    doc.status === 'UPLOADED' || doc.status === 'FAILED'
                  const isProcessingRow = actionLoadingId === doc.id

                  return (
                    <tr
                      key={doc.id}
                      onClick={() => onSelectDocument(doc.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <div className="doc-table__filename">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                          </svg>
                          <span>{doc.original_filename}</span>
                        </div>
                      </td>

                      <td>
                        <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
                          {doc.document_type || '—'}
                        </span>
                      </td>

                      <td>
                        <StatusBadge status={doc.status} />
                      </td>

                      <td>
                        {doc.overall_confidence !== null && doc.overall_confidence !== undefined ? (
                          <span
                            style={{
                              fontFamily: 'monospace',
                              fontWeight: 600,
                              color:
                                doc.overall_confidence >= 0.85
                                  ? 'var(--color-accent-success)'
                                  : doc.overall_confidence >= 0.7
                                  ? 'var(--color-accent-warning)'
                                  : 'var(--color-accent-danger)',
                            }}
                          >
                            {(doc.overall_confidence * 100).toFixed(0)}%
                          </span>
                        ) : (
                          <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                        )}
                      </td>

                      <td>
                        <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                          {formatDate(doc.created_at)}
                        </span>
                      </td>

                      <td>
                        {doc.rag_indexed ? (
                          <span
                            title="Indexed in Vector DB"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.75rem',
                              color: 'var(--color-accent-tertiary)',
                            }}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                            Indexed
                          </span>
                        ) : (
                          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>—</span>
                        )}
                      </td>

                      <td>
                        <div className="doc-table__actions" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            className="btn-icon"
                            title="View Document Details"
                            onClick={() => onSelectDocument(doc.id)}
                            aria-label={`View ${doc.original_filename}`}
                          >
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          </button>

                          {canProcess && (
                            <button
                              type="button"
                              className="btn-icon"
                              title="Start Processing Workflow"
                              onClick={(e) => handleProcessDocument(e, doc)}
                              disabled={isProcessingRow}
                              aria-label={`Process ${doc.original_filename}`}
                            >
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#4f8ef7" strokeWidth="2">
                                <polygon points="5 3 19 12 5 21 5 3" />
                              </svg>
                            </button>
                          )}

                          <button
                            type="button"
                            className="btn-icon btn-icon--danger"
                            title="Delete Document"
                            onClick={(e) => {
                              e.stopPropagation()
                              setDeleteTargetDoc(doc)
                            }}
                            aria-label={`Delete ${doc.original_filename}`}
                          >
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {/* Pagination Controls */}
            <div className="pagination-bar">
              <div>
                Showing {documents.length} of {total} documents
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                >
                  Previous
                </button>
                <span style={{ alignSelf: 'center', fontSize: '0.8125rem' }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTargetDoc)}
        title="Delete Document"
        message={`Are you sure you want to delete "${deleteTargetDoc?.original_filename}"? This action will permanently remove the stored file, extracted data, audit timeline, and vector index.`}
        confirmLabel="Delete"
        variant="danger"
        isLoading={isDeleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTargetDoc(null)}
      />
    </div>
  )
}

export default DocumentList
