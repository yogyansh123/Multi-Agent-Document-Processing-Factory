import React, { useEffect, useState, useRef, useCallback } from 'react'
import { documentsApi } from '../../api/client'
import type { ProcessingStatusResponse } from '../../types'
import {
  STAGES,
  isTerminalStatus,
  computeStageState,
  type StageState,
} from './pipelineUtils'
import './Documents.css'

export type { StageState }
export { STAGES, isTerminalStatus, computeStageState }

export interface ProcessingPipelineProps {
  documentId: string
  currentStatus: string
  ragIndexed?: boolean
  onStatusChange?: (newStatus: string) => void
}

export const ProcessingPipeline: React.FC<ProcessingPipelineProps> = ({
  documentId,
  currentStatus,
  ragIndexed,
  onStatusChange,
}) => {
  const [statusData, setStatusData] = useState<ProcessingStatusResponse | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const pollTimerRef = useRef<number | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await documentsApi.getProcessingStatus(documentId)
      setStatusData(data)

      if (onStatusChange && data.status !== currentStatus) {
        onStatusChange(data.status)
      }

      // If active processing, continue polling; if terminal, stop
      if (isTerminalStatus(data.status)) {
        setIsPolling(false)
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
      }
    } catch {
      // Backend may return 404/500 if not cached or initialized yet
      setIsPolling(false)
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [documentId, currentStatus, onStatusChange])

  useEffect(() => {
    fetchStatus()

    const active = !isTerminalStatus(currentStatus)
    setIsPolling(active)

    if (active) {
      pollTimerRef.current = window.setInterval(fetchStatus, 2000)
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [currentStatus, fetchStatus])

  return (
    <div className="pipeline-flow" aria-label="Document Processing Pipeline">
      <div className="pipeline-flow__title">
        <span>Processing Pipeline Flow</span>
        {isPolling && (
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--color-accent-warning)' }}>
            <span className="status-badge--dot" style={{ background: 'var(--color-accent-warning)' }} />
            Active Workflow Running...
          </span>
        )}
      </div>

      <div className="pipeline-stepper">
        {STAGES.map((stage, idx) => {
          const state = computeStageState(stage.key, currentStatus, statusData, ragIndexed)
          const isLast = idx === STAGES.length - 1

          return (
            <React.Fragment key={stage.key}>
              <div className={`pipeline-step pipeline-step--${state.toLowerCase()}`}>
                <div
                  className="pipeline-step__circle"
                  title={`${stage.label}: ${state === 'REVIEW_REQUIRED' ? 'Review Required' : state}`}
                >
                  {state === 'COMPLETED' ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : state === 'IN_PROGRESS' ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <circle cx="12" cy="12" r="10" strokeDasharray="32" strokeDashoffset="12" />
                    </svg>
                  ) : state === 'REVIEW_REQUIRED' ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                  ) : state === 'FAILED' ? (
                    '✕'
                  ) : (
                    idx + 1
                  )}
                </div>
                <span className="pipeline-step__label">{stage.label}</span>
              </div>

              {!isLast && (
                <div
                  className={`pipeline-connector ${
                    state === 'COMPLETED'
                      ? 'pipeline-connector--completed'
                      : state === 'IN_PROGRESS'
                      ? 'pipeline-connector--in_progress'
                      : ''
                  }`}
                  aria-hidden="true"
                />
              )}
            </React.Fragment>
          )
        })}
      </div>

      {statusData?.error_message && (
        <div style={{ marginTop: '12px', fontSize: '0.8125rem', color: '#ff859d' }}>
          <strong>Pipeline Error:</strong> {statusData.error_message}
        </div>
      )}
    </div>
  )
}

export default ProcessingPipeline
