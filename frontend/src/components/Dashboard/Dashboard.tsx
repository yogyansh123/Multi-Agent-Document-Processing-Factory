import React, { useEffect, useState, useCallback } from 'react'
import { documentsApi, reviewApi, systemApi, formatApiError } from '../../api/client'
import type {
  DocumentResponse,
  DocumentSummaryStats,
  ReviewQueueItem,
  SystemHealthResponse,
} from '../../types'
import {
  ErrorBanner,
  LoadingSpinner,
  StatusBadge,
} from '../Common'
import './DashboardPlaceholder.css'

interface DashboardProps {
  onNavigateToUpload: () => void
  onNavigateToDocuments: () => void
  onSelectDocument: (docId: string) => void
  onNavigateToReviewQueue: () => void
  onSelectReview: (reviewId: string) => void
  onNavigateToHealth: () => void
}

export const Dashboard: React.FC<DashboardProps> = ({
  onNavigateToUpload,
  onNavigateToDocuments,
  onSelectDocument,
  onNavigateToReviewQueue,
  onSelectReview,
  onNavigateToHealth,
}) => {
  const [stats, setStats] = useState<DocumentSummaryStats | null>(null)
  const [recentDocs, setRecentDocs] = useState<DocumentResponse[]>([])
  const [pendingReviews, setPendingReviews] = useState<ReviewQueueItem[]>([])
  const [health, setHealth] = useState<SystemHealthResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchDashboardData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [statsData, docsData, reviewsData, healthData] = await Promise.all([
        documentsApi.getStats(),
        documentsApi.list({ page: 1, page_size: 5 }),
        reviewApi.listQueue({ page: 1, page_size: 5, status: 'PENDING' }),
        systemApi.getDependencyHealth().catch(() => ({ status: 'unavailable' })),
      ])

      setStats(statsData)
      setRecentDocs(docsData.items)
      setPendingReviews(reviewsData.items)
      setHealth(healthData)
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboardData()
  }, [fetchDashboardData])

  const formatDate = (isoString: string): string => {
    try {
      return new Date(isoString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return isoString
    }
  }

  if (isLoading && !stats) {
    return (
      <div className="dashboard">
        <LoadingSpinner size="lg" message="Loading factory intelligence dashboard..." />
      </div>
    )
  }

  return (
    <div className="dashboard" id="dashboard-view">
      {/* Page Title & Quick Actions */}
      <div className="dashboard__header">
        <div className="dashboard__title-group">
          <h1 className="dashboard__title">
            <span className="gradient-text">Factory Control Center</span>
          </h1>
          <p className="dashboard__subtitle">
            Autonomous multi-agent document processing, validation, and retrieval analytics
          </p>
        </div>

        <div className="dashboard__actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchDashboardData}
            title="Refresh dashboard metrics"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            Refresh
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onNavigateToUpload}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Upload Document
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchDashboardData} />}

      {/* Summary KPI Metric Cards */}
      <div className="dashboard__stats-grid">
        {/* Total Documents */}
        <div className="stat-card glass" onClick={onNavigateToDocuments} style={{ cursor: 'pointer' }}>
          <div className="stat-card__header">
            <span className="stat-card__label">Total Documents</span>
            <div className="stat-card__icon" style={{ background: 'rgba(79, 142, 247, 0.15)', color: '#4f8ef7' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
          </div>
          <div className="stat-card__body">
            <span className="stat-card__value">{stats?.total_documents ?? 0}</span>
            <div className="stat-card__change stat-card__change--positive">
              <span>View document repository →</span>
            </div>
          </div>
        </div>

        {/* Processing Queue */}
        <div className="stat-card glass">
          <div className="stat-card__header">
            <span className="stat-card__label">In Processing</span>
            <div className="stat-card__icon" style={{ background: 'rgba(245, 166, 35, 0.15)', color: '#f5a623' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
            </div>
          </div>
          <div className="stat-card__body">
            <span className="stat-card__value">{stats?.processing ?? 0}</span>
            <div className="stat-card__change">
              <span>Active pipeline jobs</span>
            </div>
          </div>
        </div>

        {/* Review Queue */}
        <div className="stat-card glass" onClick={onNavigateToReviewQueue} style={{ cursor: 'pointer' }}>
          <div className="stat-card__header">
            <span className="stat-card__label">Review Required</span>
            <div className="stat-card__icon" style={{ background: 'rgba(124, 92, 252, 0.15)', color: '#7c5cfc' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
              </svg>
            </div>
          </div>
          <div className="stat-card__body">
            <span className="stat-card__value">{stats?.review_required ?? 0}</span>
            <div className="stat-card__change stat-card__change--positive">
              <span>Awaiting human auditor →</span>
            </div>
          </div>
        </div>

        {/* Average Confidence */}
        <div className="stat-card glass">
          <div className="stat-card__header">
            <span className="stat-card__label">Average Confidence</span>
            <div className="stat-card__icon" style={{ background: 'rgba(34, 197, 94, 0.15)', color: '#22c55e' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
          </div>
          <div className="stat-card__body">
            <span className="stat-card__value">
              {stats?.average_confidence !== null && stats?.average_confidence !== undefined
                ? `${(stats.average_confidence * 100).toFixed(0)}%`
                : '—'}
            </span>
            <div className="stat-card__change">
              <span>{stats?.approved ?? 0} approved documents</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Flow Visualization Card */}
      <div className="agent-pipeline glass">
        <div className="agent-pipeline__header">
          <div className="agent-pipeline__title-group">
            <h2 className="agent-pipeline__title">Multi-Agent Processing Architecture</h2>
            <p className="agent-pipeline__subtitle">
              Fully automated lifecycle orchestrated via Temporal and Redis status caching
            </p>
          </div>
          <span className="badge badge--success">
            {health?.status === 'healthy' ? 'Pipeline Operational' : health?.status?.toUpperCase() || 'Standby'}
          </span>
        </div>

        <div className="pipeline-steps">
          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">1</span>
              <span className="step-name">Ingestion</span>
              <span className="step-desc">MIME & Storage</span>
            </div>
          </div>

          <div className="pipeline-step-arrow">→</div>

          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">2</span>
              <span className="step-name">OCR Engine</span>
              <span className="step-desc">Tesseract OCR</span>
            </div>
          </div>

          <div className="pipeline-step-arrow">→</div>

          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">3</span>
              <span className="step-name">Classifier</span>
              <span className="step-desc">LangGraph Agent</span>
            </div>
          </div>

          <div className="pipeline-step-arrow">→</div>

          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">4</span>
              <span className="step-name">Extractor</span>
              <span className="step-desc">Schema Extraction</span>
            </div>
          </div>

          <div className="pipeline-step-arrow">→</div>

          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">5</span>
              <span className="step-name">Validator</span>
              <span className="step-desc">Deterministic Rules</span>
            </div>
          </div>

          <div className="pipeline-step-arrow">→</div>

          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">6</span>
              <span className="step-name">Confidence</span>
              <span className="step-desc">Decision Router</span>
            </div>
          </div>

          <div className="pipeline-step-arrow">→</div>

          <div className="pipeline-step-item">
            <div className="step-node active">
              <span className="step-num">7</span>
              <span className="step-name">RAG Index</span>
              <span className="step-desc">pgvector DB</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Dual Grid: Recent Documents & Review Alert Queue */}
      <div className="dashboard__grid">
        {/* Left: Recent Documents */}
        <div className="dashboard__card glass">
          <div className="dashboard__card-header">
            <h3 className="dashboard__card-title">Recent Documents</h3>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onNavigateToDocuments}
              style={{ fontSize: '0.75rem', padding: '4px 10px' }}
            >
              View All ({stats?.total_documents ?? 0})
            </button>
          </div>

          {recentDocs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
              No documents processed yet. Click &quot;Upload Document&quot; above to start.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
                    <th style={{ padding: '8px 12px' }}>Filename</th>
                    <th style={{ padding: '8px 12px' }}>Type</th>
                    <th style={{ padding: '8px 12px' }}>Status</th>
                    <th style={{ padding: '8px 12px' }}>Confidence</th>
                    <th style={{ padding: '8px 12px' }}>Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {recentDocs.map((doc) => (
                    <tr
                      key={doc.id}
                      onClick={() => onSelectDocument(doc.id)}
                      style={{ borderBottom: '1px solid rgba(79, 142, 247, 0.08)', cursor: 'pointer' }}
                    >
                      <td style={{ padding: '10px 12px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
                        {doc.original_filename}
                      </td>
                      <td style={{ padding: '10px 12px', color: 'var(--color-text-secondary)' }}>
                        {doc.document_type || '—'}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <StatusBadge status={doc.status} />
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>
                        {doc.overall_confidence !== null && doc.overall_confidence !== undefined
                          ? `${(doc.overall_confidence * 100).toFixed(0)}%`
                          : '—'}
                      </td>
                      <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>
                        {formatDate(doc.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: Review Queue Alerts & System Health */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Pending Reviews Box */}
          <div className="dashboard__card glass">
            <div className="dashboard__card-header">
              <h3 className="dashboard__card-title">
                Requires Human Review
                {pendingReviews.length > 0 && (
                  <span className="badge badge--warning" style={{ marginLeft: '8px' }}>
                    {pendingReviews.length}
                  </span>
                )}
              </h3>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onNavigateToReviewQueue}
                style={{ fontSize: '0.75rem', padding: '4px 10px' }}
              >
                Queue →
              </button>
            </div>

            {pendingReviews.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 16px', color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
                ✓ No documents currently require human review.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {pendingReviews.map((rev) => (
                  <div
                    key={rev.review_id}
                    onClick={() => onSelectReview(rev.review_id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 14px',
                      background: 'rgba(13, 21, 40, 0.6)',
                      borderRadius: '8px',
                      border: '1px solid var(--color-border)',
                      cursor: 'pointer',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.8125rem', color: 'var(--color-text-primary)' }}>
                        {rev.original_filename}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                        Type: {rev.document_type || 'Unclassified'} · Score: {rev.validation_score ? `${(rev.validation_score * 100).toFixed(0)}%` : '—'}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                    >
                      Audit
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* System Health Summary Widget */}
          <div className="dashboard__card glass" onClick={onNavigateToHealth} style={{ cursor: 'pointer' }}>
            <div className="dashboard__card-header">
              <h3 className="dashboard__card-title">System Infrastructure</h3>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  color: health?.status === 'healthy' ? 'var(--color-accent-success)' : 'var(--color-accent-warning)',
                }}
              >
                {health?.status?.toUpperCase() || 'HEALTHY'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
              <div style={{ padding: '8px 12px', background: 'rgba(13, 21, 40, 0.4)', borderRadius: '6px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>FastAPI Engine:</span>{' '}
                <strong style={{ color: 'var(--color-accent-success)' }}>Operational</strong>
              </div>
              <div style={{ padding: '8px 12px', background: 'rgba(13, 21, 40, 0.4)', borderRadius: '6px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>PostgreSQL:</span>{' '}
                <strong style={{ color: health?.dependencies?.postgresql === 'healthy' ? 'var(--color-accent-success)' : '#fbc770' }}>
                  {health?.dependencies?.postgresql || 'Connected'}
                </strong>
              </div>
              <div style={{ padding: '8px 12px', background: 'rgba(13, 21, 40, 0.4)', borderRadius: '6px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Redis Cache:</span>{' '}
                <strong style={{ color: health?.dependencies?.redis === 'healthy' ? 'var(--color-accent-success)' : '#fbc770' }}>
                  {health?.dependencies?.redis || 'Connected'}
                </strong>
              </div>
              <div style={{ padding: '8px 12px', background: 'rgba(13, 21, 40, 0.4)', borderRadius: '6px', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>Temporal Worker:</span>{' '}
                <strong style={{ color: health?.dependencies?.temporal === 'healthy' ? 'var(--color-accent-success)' : '#fbc770' }}>
                  {health?.dependencies?.temporal || 'Connected'}
                </strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
