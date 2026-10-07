import React, { useEffect, useState, useCallback } from 'react'
import { analyticsApi, formatApiError } from '../../api/client'
import type {
  AnalyticsSummary,
  StatusDistributionResponse,
  DocumentTypeDistributionResponse,
  ConfidenceStatistics,
  StagePerformanceResponse,
  ReviewStatistics,
  ProcessingVolumeResponse,
  RecentActivityResponse,
} from '../../types'
import { Skeleton, ErrorBanner, EmptyState, StatusBadge } from '../Common'
import './Analytics.css'

type DatePreset = '7d' | '30d' | '90d' | 'all' | 'custom'

export const AnalyticsDashboard: React.FC = () => {
  // Preset & Date Filters
  const [preset, setPreset] = useState<DatePreset>('30d')
  const [customStart, setCustomStart] = useState<string>('')
  const [customEnd, setCustomEnd] = useState<string>('')
  const [activeDateRange, setActiveDateRange] = useState<{ start?: string; end?: string }>({})

  // Volume Chart Interval: 'day' | 'week'
  const [volumeInterval, setVolumeInterval] = useState<'day' | 'week'>('day')

  // Data States
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [statusDist, setStatusDist] = useState<StatusDistributionResponse | null>(null)
  const [typeDist, setTypeDist] = useState<DocumentTypeDistributionResponse | null>(null)
  const [confidenceStats, setConfidenceStats] = useState<ConfidenceStatistics | null>(null)
  const [stagePerf, setStagePerf] = useState<StagePerformanceResponse | null>(null)
  const [reviewStats, setReviewStats] = useState<ReviewStatistics | null>(null)
  const [volume, setVolume] = useState<ProcessingVolumeResponse | null>(null)
  const [recentActivity, setRecentActivity] = useState<RecentActivityResponse | null>(null)

  // Loading, Refreshing, & Error
  const [loading, setLoading] = useState<boolean>(true)
  const [refreshing, setRefreshing] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date>(new Date())

  // Calculate ISO range from preset
  const calculatePresetRange = useCallback((selectedPreset: DatePreset): { start?: string; end?: string } => {
    if (selectedPreset === 'all') {
      return {}
    }
    const end = new Date()
    const start = new Date()

    if (selectedPreset === '7d') {
      start.setDate(end.getDate() - 7)
    } else if (selectedPreset === '30d') {
      start.setDate(end.getDate() - 30)
    } else if (selectedPreset === '90d') {
      start.setDate(end.getDate() - 90)
    }
    return {
      start: start.toISOString(),
      end: end.toISOString(),
    }
  }, [])

  // Update active range on preset change
  useEffect(() => {
    if (preset !== 'custom') {
      setActiveDateRange(calculatePresetRange(preset))
    }
  }, [preset, calculatePresetRange])

  // Fetch all analytics in parallel
  const fetchAnalytics = useCallback(async (isBackground = false) => {
    if (isBackground) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    const { start, end } = activeDateRange

    try {
      const [
        summaryRes,
        statusRes,
        typeRes,
        confidenceRes,
        stagesRes,
        reviewsRes,
        volumeRes,
        activityRes,
      ] = await Promise.all([
        analyticsApi.getAnalyticsSummary(start, end),
        analyticsApi.getStatusDistribution(start, end),
        analyticsApi.getDocumentTypes(start, end),
        analyticsApi.getConfidenceStatistics(start, end),
        analyticsApi.getStagePerformance(start, end),
        analyticsApi.getReviewStatistics(start, end),
        analyticsApi.getProcessingVolume(start, end, volumeInterval),
        analyticsApi.getRecentActivity(20),
      ])

      setSummary(summaryRes)
      setStatusDist(statusRes)
      setTypeDist(typeRes)
      setConfidenceStats(confidenceRes)
      setStagePerf(stagesRes)
      setReviewStats(reviewsRes)
      setVolume(volumeRes)
      setRecentActivity(activityRes)
      setLastRefreshedAt(new Date())
    } catch (err) {
      setError(formatApiError(err))
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [activeDateRange, volumeInterval])

  // Initial & Dependency Fetch
  useEffect(() => {
    fetchAnalytics()
  }, [fetchAnalytics])

  // Auto-refresh every 60 seconds while mounted
  useEffect(() => {
    const timer = setInterval(() => {
      fetchAnalytics(true)
    }, 60000)

    return () => clearInterval(timer)
  }, [fetchAnalytics])

  // Custom date range submit handler
  const handleApplyCustomRange = (e: React.FormEvent) => {
    e.preventDefault()
    if (!customStart || !customEnd) return

    if (new Date(customStart) > new Date(customEnd)) {
      setError('Start date cannot be after end date.')
      return
    }

    setActiveDateRange({
      start: new Date(customStart).toISOString(),
      end: new Date(customEnd).toISOString(),
    })
  }

  // Navigate to document cockpit
  const handleNavigateDocument = (docId: string, e: React.MouseEvent) => {
    e.preventDefault()
    window.history.pushState({}, '', `/documents/${docId}`)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }

  // Render Status Color Class Helper
  const getStatusColorClass = (status: string): string => {
    switch (status.toUpperCase()) {
      case 'APPROVED': return 'fill-approved'
      case 'REVIEW_REQUIRED': return 'fill-review'
      case 'REJECTED': return 'fill-rejected'
      case 'PROCESSING':
      case 'OCR_COMPLETED':
      case 'CLASSIFIED':
      case 'EXTRACTED':
      case 'VALIDATED': return 'fill-processing'
      case 'FAILED': return 'fill-failed'
      default: return 'fill-other'
    }
  }

  // Render Document Type Color Class Helper
  const getTypeColorClass = (type: string): string => {
    switch (type.toUpperCase()) {
      case 'INVOICE': return 'fill-invoice'
      case 'RECEIPT': return 'fill-receipt'
      case 'PURCHASE_ORDER': return 'fill-po'
      case 'CONTRACT': return 'fill-contract'
      default: return 'fill-other'
    }
  }

  return (
    <div className="analytics-dashboard" aria-label="Analytics & Observability Dashboard">
      {/* Header & Controls */}
      <header className="analytics-header">
        <div className="analytics-header-top">
          <div className="analytics-title-group">
            <h1>Analytics & Observability</h1>
            <p className="analytics-subtitle">
              Live processing telemetry, pipeline performance, confidence metrics, and throughput.
            </p>
          </div>

          <div className="analytics-header-actions">
            <span className="auto-refresh-badge" title="Auto-refreshes every 60 seconds">
              <span className="auto-refresh-dot" />
              Live Telemetry
            </span>

            <button
              type="button"
              className="btn-refresh"
              onClick={() => fetchAnalytics(true)}
              disabled={refreshing || loading}
              aria-label="Refresh analytics data"
            >
              <span className={refreshing ? 'spin-icon' : ''}>🔄</span>
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Date Filter Controls */}
        <div className="analytics-controls-bar">
          <div className="preset-filters" role="group" aria-label="Date range presets">
            {(['7d', '30d', '90d', 'all', 'custom'] as DatePreset[]).map((p) => (
              <button
                key={p}
                type="button"
                className={`preset-btn ${preset === p ? 'active' : ''}`}
                onClick={() => setPreset(p)}
                aria-pressed={preset === p}
              >
                {p === '7d' && 'Last 7 Days'}
                {p === '30d' && 'Last 30 Days'}
                {p === '90d' && 'Last 90 Days'}
                {p === 'all' && 'All Time'}
                {p === 'custom' && 'Custom Range'}
              </button>
            ))}
          </div>

          {preset === 'custom' && (
            <form className="custom-range-inputs" onSubmit={handleApplyCustomRange}>
              <label className="custom-date-label">
                From:
                <input
                  type="date"
                  className="custom-date-input"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                  required
                />
              </label>
              <label className="custom-date-label">
                To:
                <input
                  type="date"
                  className="custom-date-input"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  required
                />
              </label>
              <button type="submit" className="apply-range-btn">
                Apply
              </button>
            </form>
          )}

          <div className="volume-legend">
            <span>Last synced: {lastRefreshedAt.toLocaleTimeString()}</span>
          </div>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <ErrorBanner
          message={error}
          onRetry={() => fetchAnalytics(false)}
        />
      )}

      {/* Loading Skeletons */}
      {loading && (
        <div className="analytics-loading-state" aria-busy="true">
          <div className="kpi-grid">
            {Array.from({ length: 7 }).map((_, i) => (
              <Skeleton key={i} height="110px" borderRadius="var(--radius-lg)" />
            ))}
          </div>
          <div className="analytics-two-col" style={{ marginTop: 'var(--space-6)' }}>
            <Skeleton height="320px" borderRadius="var(--radius-lg)" />
            <Skeleton height="320px" borderRadius="var(--radius-lg)" />
          </div>
        </div>
      )}

      {!loading && summary && summary.total_documents === 0 && (
        <EmptyState
          title="No Document Data Available"
          description="Upload documents and initiate workflow processing to generate real-time observability metrics."
          action={{
            label: 'Upload Documents',
            onClick: () => {
              window.history.pushState({}, '', '/upload')
              window.dispatchEvent(new PopStateEvent('popstate'))
            },
          }}
        />
      )}

      {!loading && summary && summary.total_documents > 0 && (
        <>
          {/* SECTION 1 — KPI CARDS */}
          <section className="kpi-grid" aria-label="Key Performance Indicators">
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>Total Documents</span>
                <span className="kpi-icon">📄</span>
              </div>
              <div className="kpi-value">{summary.total_documents}</div>
              <div className="kpi-subtext">Active & processed</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>Approved</span>
                <span className="kpi-icon">✅</span>
              </div>
              <div className="kpi-value" style={{ color: 'var(--color-accent-success)' }}>
                {summary.approved_documents}
              </div>
              <div className="kpi-subtext">
                {summary.auto_approved_documents} auto-approved
              </div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>Review Required</span>
                <span className="kpi-icon">⚠️</span>
              </div>
              <div className="kpi-value" style={{ color: 'var(--color-accent-warning)' }}>
                {summary.review_required_documents}
              </div>
              <div className="kpi-subtext">Awaiting human review</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>Rejected</span>
                <span className="kpi-icon">🛑</span>
              </div>
              <div className="kpi-value" style={{ color: 'var(--color-accent-danger)' }}>
                {summary.rejected_documents}
              </div>
              <div className="kpi-subtext">Declined by review</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>Average Confidence</span>
                <span className="kpi-icon">🎯</span>
              </div>
              <div className="kpi-value">
                {summary.average_confidence !== null
                  ? `${Math.round(summary.average_confidence * 100)}%`
                  : 'N/A'}
              </div>
              <div className="kpi-subtext">Weighted multi-agent score</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>Avg Stage Latency</span>
                <span className="kpi-icon">⏱️</span>
              </div>
              <div className="kpi-value">
                {summary.average_processing_time_ms !== null
                  ? `${(summary.average_processing_time_ms / 1000).toFixed(2)}s`
                  : 'N/A'}
              </div>
              <div className="kpi-subtext">Per completed stage</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <span>RAG Vector Indexed</span>
                <span className="kpi-icon">🧠</span>
              </div>
              <div className="kpi-value" style={{ color: 'var(--color-accent-primary)' }}>
                {summary.rag_indexed_documents}
              </div>
              <div className="kpi-subtext">Available for semantic Q&A</div>
            </div>
          </section>

          {/* SECTION 2 & 3 — DOCUMENT STATUS & DOCUMENT TYPES */}
          <div className="analytics-two-col">
            {/* Section 2: Document Status Distribution */}
            <div className="analytics-card" aria-label="Document Status Distribution">
              <div className="analytics-card-title">
                <span>Document Status Breakdown</span>
                <span className="analytics-badge-count">{statusDist?.total || 0} Total</span>
              </div>

              <div className="distribution-list">
                {statusDist?.items.map((item) => (
                  <div key={item.status} className="distribution-item">
                    <div className="distribution-info">
                      <span>{item.status.replace(/_/g, ' ')}</span>
                      <span>
                        <strong>{item.count}</strong> ({item.percentage}%)
                      </span>
                    </div>
                    <div className="distribution-bar-bg">
                      <div
                        className={`distribution-bar-fill ${getStatusColorClass(item.status)}`}
                        style={{ width: `${Math.min(100, Math.max(item.count > 0 ? 3 : 0, item.percentage))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 3: Document Types Distribution */}
            <div className="analytics-card" aria-label="Document Types Distribution">
              <div className="analytics-card-title">
                <span>Classified Document Types</span>
                <span className="analytics-badge-count">{typeDist?.total || 0} Classified</span>
              </div>

              <div className="distribution-list">
                {typeDist?.items.map((item) => (
                  <div key={item.document_type} className="distribution-item">
                    <div className="distribution-info">
                      <span>{item.document_type.replace(/_/g, ' ')}</span>
                      <span>
                        <strong>{item.count}</strong> ({item.percentage}%)
                      </span>
                    </div>
                    <div className="distribution-bar-bg">
                      <div
                        className={`distribution-bar-fill ${getTypeColorClass(item.document_type)}`}
                        style={{ width: `${Math.min(100, Math.max(item.count > 0 ? 3 : 0, item.percentage))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Confidence Health Breakdown */}
          {confidenceStats && (
            <section className="analytics-card" aria-label="Confidence Metrics Breakdown">
              <div className="analytics-card-title">
                <span>Confidence Factor Breakdown</span>
                <span className="analytics-badge-count">
                  {confidenceStats.auto_approve_count} Auto-Approve / {confidenceStats.review_required_count} Review Req.
                </span>
              </div>

              <div className="review-stats-grid">
                <div className="review-stat-box">
                  <span className="review-stat-label">Overall Avg</span>
                  <span className="review-stat-num">
                    {confidenceStats.average_overall !== null
                      ? `${Math.round(confidenceStats.average_overall * 100)}%`
                      : '—'}
                  </span>
                </div>

                <div className="review-stat-box">
                  <span className="review-stat-label">Classification Avg</span>
                  <span className="review-stat-num">
                    {confidenceStats.average_classification !== null
                      ? `${Math.round(confidenceStats.average_classification * 100)}%`
                      : '—'}
                  </span>
                </div>

                <div className="review-stat-box">
                  <span className="review-stat-label">Extraction Avg</span>
                  <span className="review-stat-num">
                    {confidenceStats.average_extraction !== null
                      ? `${Math.round(confidenceStats.average_extraction * 100)}%`
                      : '—'}
                  </span>
                </div>

                <div className="review-stat-box">
                  <span className="review-stat-label">Validation Avg</span>
                  <span className="review-stat-num">
                    {confidenceStats.average_validation !== null
                      ? `${Math.round(confidenceStats.average_validation * 100)}%`
                      : '—'}
                  </span>
                </div>

                <div className="review-stat-box">
                  <span className="review-stat-label">Min Recorded</span>
                  <span className="review-stat-num" style={{ color: 'var(--color-accent-warning)' }}>
                    {confidenceStats.min_confidence !== null
                      ? `${Math.round(confidenceStats.min_confidence * 100)}%`
                      : '—'}
                  </span>
                </div>

                <div className="review-stat-box">
                  <span className="review-stat-label">Max Recorded</span>
                  <span className="review-stat-num" style={{ color: 'var(--color-accent-success)' }}>
                    {confidenceStats.max_confidence !== null
                      ? `${Math.round(confidenceStats.max_confidence * 100)}%`
                      : '—'}
                  </span>
                </div>
              </div>
            </section>
          )}

          {/* SECTION 4 — PIPELINE PERFORMANCE */}
          <section className="analytics-card" aria-label="Pipeline Stage Performance">
            <div className="analytics-card-title">
              <span>Pipeline Stage Observability</span>
              <span className="analytics-badge-count">
                {stagePerf?.total_executions || 0} Stage Executions
              </span>
            </div>

            <div className="stages-grid">
              {stagePerf?.stages.map((stage) => (
                <div key={stage.stage} className="stage-card">
                  <div className="stage-card-header">
                    <span className="stage-name">{stage.stage}</span>
                    <span
                      style={{
                        fontSize: 'var(--text-xs)',
                        fontWeight: 'bold',
                        color:
                          stage.success_rate >= 90
                            ? 'var(--color-accent-success)'
                            : stage.success_rate >= 70
                            ? 'var(--color-accent-warning)'
                            : 'var(--color-accent-danger)',
                      }}
                    >
                      {stage.success_rate}%
                    </span>
                  </div>

                  <div className="stage-metric-row">
                    <span>Executions:</span>
                    <span className="stage-metric-value">{stage.executions}</span>
                  </div>

                  <div className="stage-metric-row">
                    <span>Success / Fail:</span>
                    <span className="stage-metric-value">
                      {stage.completed} / {stage.failed}
                    </span>
                  </div>

                  <div className="stage-metric-row">
                    <span>Avg Latency:</span>
                    <span className="stage-metric-value">
                      {stage.average_duration_ms !== null
                        ? `${stage.average_duration_ms.toFixed(0)} ms`
                        : '—'}
                    </span>
                  </div>

                  <div className="stage-success-meter">
                    <div className="distribution-bar-bg">
                      <div
                        className="distribution-bar-fill"
                        style={{
                          width: `${stage.success_rate}%`,
                          background:
                            stage.success_rate >= 90
                              ? 'var(--color-accent-success)'
                              : stage.success_rate >= 70
                              ? 'var(--color-accent-warning)'
                              : 'var(--color-accent-danger)',
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* SECTION 5 — PROCESSING VOLUME TIME SERIES */}
          <section className="analytics-card" aria-label="Processing Volume Over Time">
            <div className="volume-chart-toolbar">
              <div className="analytics-card-title">
                <span>Processing Throughput Over Time</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                <div className="volume-legend">
                  <div className="legend-item">
                    <span className="legend-color" style={{ background: 'var(--color-accent-primary)' }} />
                    <span>Total</span>
                  </div>
                  <div className="legend-item">
                    <span className="legend-color" style={{ background: 'var(--color-accent-success)' }} />
                    <span>Completed</span>
                  </div>
                  <div className="legend-item">
                    <span className="legend-color" style={{ background: 'var(--color-accent-danger)' }} />
                    <span>Failed</span>
                  </div>
                </div>

                <div className="preset-filters" role="group" aria-label="Volume aggregation interval">
                  <button
                    type="button"
                    className={`preset-btn ${volumeInterval === 'day' ? 'active' : ''}`}
                    onClick={() => setVolumeInterval('day')}
                  >
                    Daily
                  </button>
                  <button
                    type="button"
                    className={`preset-btn ${volumeInterval === 'week' ? 'active' : ''}`}
                    onClick={() => setVolumeInterval('week')}
                  >
                    Weekly
                  </button>
                </div>
              </div>
            </div>

            <div className="svg-chart-wrapper">
              {volume && volume.points.length > 0 ? (
                <svg
                  className="svg-chart"
                  viewBox="0 0 800 200"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label="Throughput bar chart"
                >
                  {/* Grid Lines */}
                  <line x1="40" y1="40" x2="780" y2="40" className="chart-grid-line" />
                  <line x1="40" y1="90" x2="780" y2="90" className="chart-grid-line" />
                  <line x1="40" y1="140" x2="780" y2="140" className="chart-grid-line" />
                  <line x1="40" y1="170" x2="780" y2="170" stroke="rgba(255, 255, 255, 0.2)" />

                  {/* Dynamic Bars */}
                  {(() => {
                    const maxVal = Math.max(1, ...volume.points.map((p) => p.total))
                    const barWidth = Math.max(12, Math.min(36, 700 / (volume.points.length * 1.5)))

                    return volume.points.map((pt, idx) => {
                      const x = 50 + idx * (720 / volume.points.length)
                      const barHeight = (pt.total / maxVal) * 120
                      const y = 170 - barHeight
                      const compHeight = (pt.completed / maxVal) * 120
                      const compY = 170 - compHeight

                      return (
                        <g key={pt.period}>
                          {/* Total Bar */}
                          <rect
                            x={x}
                            y={y}
                            width={barWidth}
                            height={Math.max(2, barHeight)}
                            fill="var(--color-accent-primary)"
                            rx="3"
                            className="chart-bar"
                          >
                            <title>{`${pt.period}: ${pt.total} total, ${pt.completed} completed, ${pt.failed} failed`}</title>
                          </rect>

                          {/* Completed Sub-Bar */}
                          {pt.completed > 0 && (
                            <rect
                              x={x}
                              y={compY}
                              width={barWidth}
                              height={Math.max(2, compHeight)}
                              fill="var(--color-accent-success)"
                              rx="3"
                              className="chart-bar"
                            >
                              <title>{`${pt.period}: ${pt.completed} completed`}</title>
                            </rect>
                          )}

                          {/* X-axis Label */}
                          <text x={x + barWidth / 2} y={188} className="chart-axis-label">
                            {pt.period.length > 5 ? pt.period.slice(5) : pt.period}
                          </text>
                        </g>
                      )
                    })
                  })()}
                </svg>
              ) : (
                <div
                  style={{
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--color-text-muted)',
                    fontSize: 'var(--text-sm)',
                  }}
                >
                  No volume data found for the selected time range.
                </div>
              )}
            </div>
          </section>

          {/* SECTION 6 — HUMAN REVIEW WORKLOAD */}
          <section className="analytics-card" aria-label="Human Review Queue Workload">
            <div className="analytics-card-title">
              <span>Human Review Operations</span>
              <span className="analytics-badge-count">
                {reviewStats?.total_reviews || 0} Total Reviews
              </span>
            </div>

            <div className="review-stats-grid">
              <div className="review-stat-box">
                <span className="review-stat-label">Pending</span>
                <span className="review-stat-num" style={{ color: 'var(--color-accent-warning)' }}>
                  {reviewStats?.pending_reviews || 0}
                </span>
              </div>

              <div className="review-stat-box">
                <span className="review-stat-label">In Review</span>
                <span className="review-stat-num" style={{ color: 'var(--color-accent-primary)' }}>
                  {reviewStats?.in_review || 0}
                </span>
              </div>

              <div className="review-stat-box">
                <span className="review-stat-label">Completed</span>
                <span className="review-stat-num" style={{ color: 'var(--color-accent-success)' }}>
                  {reviewStats?.completed_reviews || 0}
                </span>
              </div>

              <div className="review-stat-box">
                <span className="review-stat-label">Approved</span>
                <span className="review-stat-num">
                  {reviewStats?.approved_reviews || 0}
                </span>
              </div>

              <div className="review-stat-box">
                <span className="review-stat-label">Corrected</span>
                <span className="review-stat-num" style={{ color: 'var(--color-accent-tertiary)' }}>
                  {reviewStats?.corrected_reviews || 0}
                </span>
              </div>

              <div className="review-stat-box">
                <span className="review-stat-label">Rejected</span>
                <span className="review-stat-num" style={{ color: 'var(--color-accent-danger)' }}>
                  {reviewStats?.rejected_reviews || 0}
                </span>
              </div>

              <div className="review-stat-box">
                <span className="review-stat-label">Avg Resolution</span>
                <span className="review-stat-num">
                  {reviewStats?.average_review_time_seconds !== null && reviewStats?.average_review_time_seconds !== undefined
                    ? `${reviewStats.average_review_time_seconds.toFixed(0)}s`
                    : '—'}
                </span>
              </div>
            </div>
          </section>

          {/* SECTION 7 — RECENT ACTIVITY */}
          <section className="analytics-card" aria-label="Recent Processing History Events">
            <div className="analytics-card-title">
              <span>Recent Activity Stream</span>
              <span className="analytics-badge-count">
                Latest {recentActivity?.items.length || 0} Events
              </span>
            </div>

            <div className="recent-activity-table-wrapper">
              <table className="activity-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Stage</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Timestamp</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {recentActivity && recentActivity.items.length > 0 ? (
                    recentActivity.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <a
                            href={`/documents/${item.document_id}`}
                            onClick={(e) => handleNavigateDocument(item.document_id, e)}
                            className="activity-doc-link"
                          >
                            {item.document_filename}
                          </a>
                        </td>
                        <td>
                          <span style={{ fontWeight: 'var(--weight-semibold)', color: 'var(--color-text-primary)' }}>
                            {item.stage}
                          </span>
                        </td>
                        <td>
                          <StatusBadge status={item.status} />
                        </td>
                        <td>
                          {item.duration_ms !== null && item.duration_ms !== undefined
                            ? `${item.duration_ms.toFixed(0)} ms`
                            : '—'}
                        </td>
                        <td>
                          {item.started_at
                            ? new Date(item.started_at).toLocaleString()
                            : item.completed_at
                            ? new Date(item.completed_at).toLocaleString()
                            : '—'}
                        </td>
                        <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.message || '—'}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: 'var(--space-6)' }}>
                        No recent processing events recorded.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
