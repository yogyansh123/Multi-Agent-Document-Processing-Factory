import React, { useState, useEffect, useCallback } from 'react'
import { systemApi, formatApiError } from '../../api/client'
import type { SystemHealthResponse } from '../../types'
import { ErrorBanner, LoadingSpinner } from '../Common'
import './SystemHealth.css'

export const SystemHealth: React.FC = () => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null)
  const [lastChecked, setLastChecked] = useState<Date>(new Date())
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchHealth = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await systemApi.getDependencyHealth()
      setHealth(data)
      setLastChecked(new Date())
    } catch (err) {
      setError(formatApiError(err))
      setHealth({
        status: 'unavailable',
        dependencies: {
          postgresql: 'unavailable',
          redis: 'unavailable',
          temporal: 'unavailable',
        },
      })
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
  }, [fetchHealth])

  const getStatusBadge = (status?: string) => {
    const s = (status || '').toLowerCase()
    if (s === 'healthy') {
      return <span className="health-pill health-pill--healthy">Operational</span>
    }
    if (s === 'degraded') {
      return <span className="health-pill health-pill--degraded">Degraded</span>
    }
    return <span className="health-pill health-pill--unavailable">Unavailable</span>
  }

  return (
    <div className="doc-page">
      <div className="doc-header">
        <div>
          <h1 className="doc-header__title">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
            System Health & Infrastructure
          </h1>
          <p className="doc-header__subtitle">
            Real-time status monitoring for core backend services, databases, workflow orchestrator, and cache.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={fetchHealth}
          disabled={isLoading}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
          </svg>
          Refresh Health Checks
        </button>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchHealth} />}

      {/* Primary Status Banner */}
      <div className="system-overview-card glass">
        <div className="system-overview__left">
          <span className="system-overview__label">Platform Core Status</span>
          <div className="system-overview__val">
            <span
              className={`health-dot health-dot--${(health?.status || 'unavailable').toLowerCase()}`}
            />
            {health?.status ? health.status.toUpperCase() : 'CHECKING...'}
          </div>
        </div>

        <div className="system-overview__right">
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
            Last verified: {lastChecked.toLocaleTimeString()}
          </span>
        </div>
      </div>

      {isLoading && !health ? (
        <LoadingSpinner message="Checking dependency statuses..." />
      ) : (
        /* Dependencies Grid */
        <div className="system-deps-grid">
          {/* FastAPI Application */}
          <div className="dep-card glass">
            <div className="dep-card__header">
              <div className="dep-card__title">
                <div className="dep-card__icon" style={{ background: 'rgba(79, 142, 247, 0.15)', color: '#4f8ef7' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
                    <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
                    <line x1="6" y1="6" x2="6.01" y2="6" />
                    <line x1="6" y1="18" x2="6.01" y2="18" />
                  </svg>
                </div>
                <div>
                  <h3 className="dep-card__name">FastAPI Core Engine</h3>
                  <span className="dep-card__desc">REST API, Pydantic validation, CORS</span>
                </div>
              </div>
              {getStatusBadge('healthy')}
            </div>
            <div className="dep-card__body">
              <div className="dep-card__row">
                <span>Protocol</span>
                <strong>HTTP / JSON</strong>
              </div>
              <div className="dep-card__row">
                <span>Route Prefix</span>
                <code style={{ fontSize: '0.75rem' }}>/api/v1</code>
              </div>
              <div className="dep-card__row">
                <span>Readiness</span>
                <span style={{ color: 'var(--color-accent-success)' }}>Serving requests</span>
              </div>
            </div>
          </div>

          {/* PostgreSQL + pgvector */}
          <div className="dep-card glass">
            <div className="dep-card__header">
              <div className="dep-card__title">
                <div className="dep-card__icon" style={{ background: 'rgba(124, 92, 252, 0.15)', color: '#7c5cfc' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <ellipse cx="12" cy="5" rx="9" ry="3" />
                    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                  </svg>
                </div>
                <div>
                  <h3 className="dep-card__name">PostgreSQL + pgvector</h3>
                  <span className="dep-card__desc">Relational DB & vector store</span>
                </div>
              </div>
              {getStatusBadge(health?.dependencies?.postgresql)}
            </div>
            <div className="dep-card__body">
              <div className="dep-card__row">
                <span>Check</span>
                <code>SELECT 1</code>
              </div>
              <div className="dep-card__row">
                <span>Features</span>
                <span>ACID, JSONB, Vector HNSW</span>
              </div>
              <div className="dep-card__row">
                <span>Status</span>
                <span>{health?.dependencies?.postgresql === 'healthy' ? 'Connected' : 'Unavailable'}</span>
              </div>
            </div>
          </div>

          {/* Redis */}
          <div className="dep-card glass">
            <div className="dep-card__header">
              <div className="dep-card__title">
                <div className="dep-card__icon" style={{ background: 'rgba(255, 77, 109, 0.15)', color: '#ff4d6d' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                  </svg>
                </div>
                <div>
                  <h3 className="dep-card__name">Redis Status Cache</h3>
                  <span className="dep-card__desc">In-memory pipeline status & TTL</span>
                </div>
              </div>
              {getStatusBadge(health?.dependencies?.redis)}
            </div>
            <div className="dep-card__body">
              <div className="dep-card__row">
                <span>Check</span>
                <code>PING / PONG</code>
              </div>
              <div className="dep-card__row">
                <span>Key Prefix</span>
                <code style={{ fontSize: '0.75rem' }}>document:status:*</code>
              </div>
              <div className="dep-card__row">
                <span>Cache TTL</span>
                <span>3600 seconds</span>
              </div>
            </div>
          </div>

          {/* Temporal */}
          <div className="dep-card glass">
            <div className="dep-card__header">
              <div className="dep-card__title">
                <div className="dep-card__icon" style={{ background: 'rgba(0, 212, 170, 0.15)', color: '#00d4aa' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </div>
                <div>
                  <h3 className="dep-card__name">Temporal Orchestration</h3>
                  <span className="dep-card__desc">Durable multi-agent workflows</span>
                </div>
              </div>
              {getStatusBadge(health?.dependencies?.temporal)}
            </div>
            <div className="dep-card__body">
              <div className="dep-card__row">
                <span>Task Queue</span>
                <code>doc-processing-queue</code>
              </div>
              <div className="dep-card__row">
                <span>Workflow Idempotency</span>
                <span>Deterministic</span>
              </div>
              <div className="dep-card__row">
                <span>Status</span>
                <span>{health?.dependencies?.temporal === 'healthy' ? 'Worker Listening' : 'Offline / Standby'}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SystemHealth
