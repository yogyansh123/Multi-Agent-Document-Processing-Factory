import React, { useState, useEffect, useCallback } from 'react'
import type { ReviewQueueItem, ReviewQueueResponse } from './types'

interface ReviewQueueProps {
  onSelectReview: (reviewId: string) => void
}

export const ReviewQueue: React.FC<ReviewQueueProps> = ({ onSelectReview }) => {
  const [items, setItems] = useState<ReviewQueueItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [totalPages, setTotalPages] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('PENDING')
  const [docTypeFilter, setDocTypeFilter] = useState<string>('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchQueue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      params.append('page', page.toString())
      params.append('page_size', pageSize.toString())
      if (statusFilter && statusFilter !== 'ALL') {
        params.append('status', statusFilter)
      } else if (statusFilter === 'ALL') {
        params.append('status', 'ALL')
      }
      if (docTypeFilter && docTypeFilter !== 'ALL') {
        params.append('document_type', docTypeFilter)
      }

      const res = await fetch(`/api/v1/review/queue?${params.toString()}`)
      if (!res.ok) {
        throw new Error(`Failed to load review queue: ${res.status} ${res.statusText}`)
      }
      const data: ReviewQueueResponse = await res.json()
      setItems(data.items || [])
      setTotal(data.total || 0)
      setTotalPages(data.total_pages || 1)
    } catch (err: any) {
      setError(err.message || 'An error occurred while fetching the review queue.')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, statusFilter, docTypeFilter])

  useEffect(() => {
    fetchQueue()
  }, [fetchQueue])

  const formatConfidence = (val: number | null) => {
    if (val === null || val === undefined) return 'N/A'
    return `${(val * 100).toFixed(1)}%`
  }

  const formatScore = (val: number | null) => {
    if (val === null || val === undefined) return 'N/A'
    return `${(val * 100).toFixed(0)}%`
  }

  const getStatusBadgeClass = (status: string) => {
    switch (status.toUpperCase()) {
      case 'PENDING':
        return 'badge-pending'
      case 'IN_REVIEW':
        return 'badge-in_review'
      case 'COMPLETED':
      case 'APPROVED':
        return 'badge-completed'
      case 'REJECTED':
        return 'badge-rejected'
      default:
        return 'badge-info'
    }
  }

  return (
    <div className="review-container" id="review-queue-view">
      <div className="review-header">
        <div className="review-title-group">
          <h1>Human Review Queue</h1>
          <p className="review-subtitle">
            Inspect, approve, or correct documents requiring human verification
          </p>
        </div>
        <div className="review-actions-header">
          <button
            id="refresh-review-queue-btn"
            className="btn btn-secondary"
            onClick={fetchQueue}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : '↻ Refresh'}
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="review-filters" role="search" aria-label="Review Queue Filters">
        <div className="filter-group">
          <label htmlFor="filter-review-status" className="filter-label">Status</label>
          <select
            id="filter-review-status"
            className="filter-select"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
          >
            <option value="PENDING">Pending</option>
            <option value="IN_REVIEW">In Review</option>
            <option value="COMPLETED">Completed</option>
            <option value="ALL">All Statuses</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-review-doc-type" className="filter-label">Document Type</label>
          <select
            id="filter-review-doc-type"
            className="filter-select"
            value={docTypeFilter}
            onChange={(e) => {
              setDocTypeFilter(e.target.value)
              setPage(1)
            }}
          >
            <option value="">All Types</option>
            <option value="INVOICE">Invoice</option>
            <option value="RECEIPT">Receipt</option>
            <option value="PURCHASE_ORDER">Purchase Order</option>
            <option value="CONTRACT">Contract</option>
            <option value="OTHER">Other</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', color: 'var(--color-text-secondary)', fontSize: 'var(--text-xs)' }}>
          Showing {items.length} of {total} {total === 1 ? 'item' : 'items'}
        </div>
      </div>

      {/* Content State */}
      {error && (
        <div className="glass-card" style={{ borderLeft: '4px solid var(--color-accent-danger)' }}>
          <p style={{ color: 'var(--color-accent-danger)' }}>{error}</p>
        </div>
      )}

      {loading && items.length === 0 ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: 'var(--space-12)' }}>
          <p style={{ color: 'var(--color-text-secondary)' }}>Loading review queue...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="glass-card" style={{ textAlign: 'center', padding: 'var(--space-12)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '8px' }}>✓</div>
          <h3 style={{ marginBottom: '4px' }}>Queue is Clear</h3>
          <p style={{ color: 'var(--color-text-secondary)' }}>
            No documents matching the selected criteria require human review.
          </p>
        </div>
      ) : (
        <>
          <div className="review-table-container">
            <table className="review-table" aria-label="Review Queue Table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Review Status</th>
                  <th>Confidence</th>
                  <th>Validation</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.review_id} id={`review-row-${item.review_id}`}>
                    <td>
                      <div className="filename-cell">
                        <span className="file-icon">📄</span>
                        <div>
                          <div style={{ fontWeight: 600 }}>{item.original_filename}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)' }}>
                            {item.document_id.slice(0, 8)}...
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-doc-type">
                        {item.document_type || 'UNKNOWN'}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(item.status)}`}>
                        {item.status}
                      </span>
                    </td>
                    <td>
                      <div>
                        <span style={{ fontWeight: 600, color: (item.overall_confidence ?? 0) >= 0.85 ? '#22c55e' : '#f5a623' }}>
                          {formatConfidence(item.overall_confidence)}
                        </span>
                        <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
                          {item.confidence_recommendation || 'REVIEW_REQUIRED'}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontWeight: 500 }}>
                        {formatScore(item.validation_score)}
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        id={`btn-review-${item.review_id}`}
                        className="btn btn-primary"
                        style={{ padding: '6px 14px', fontSize: '12px' }}
                        onClick={() => onSelectReview(item.review_id)}
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="pagination-bar">
            <span>
              Page {page} of {totalPages} ({total} total)
            </span>
            <div className="pagination-controls">
              <button
                className="btn btn-secondary"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <button
                className="btn btn-secondary"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default ReviewQueue
