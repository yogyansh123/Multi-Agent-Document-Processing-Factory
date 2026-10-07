import React, { useState, useEffect, useCallback } from 'react'
import type { ReviewDetailsResponse } from './types'
import ExtractedDataEditor from './ExtractedDataEditor'
import { reviewApi, formatApiError } from '../../api/client'

interface ReviewDetailsProps {
  reviewId: string
  onBack: () => void
}

export const ReviewDetails: React.FC<ReviewDetailsProps> = ({ reviewId, onBack }) => {
  const [review, setReview] = useState<ReviewDetailsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Local state for editable extraction data
  const [editableData, setEditableData] = useState<Record<string, any>>({})
  const [decisionReason, setDecisionReason] = useState('')
  const [reviewerName, setReviewerName] = useState('')


  // Modals / dialogs
  const [showApproveModal, setShowApproveModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [showCorrectModal, setShowCorrectModal] = useState(false)

  const fetchDetails = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await reviewApi.getDetails(reviewId)
      setReview(data as unknown as ReviewDetailsResponse)
      // Initialize editable data from reviewed or extracted data
      const initialExtraction =
        data.reviewed_extracted_data || data.document.extracted_data || data.original_extracted_data || {}
      setEditableData(JSON.parse(JSON.stringify(initialExtraction)))
    } catch (err: unknown) {
      setError(formatApiError(err) || 'Failed to load review details.')
    } finally {
      setLoading(false)
    }
  }, [reviewId])

  useEffect(() => {
    fetchDetails()
  }, [fetchDetails])

  const handleStartReview = async () => {
    setActionLoading(true)
    setError(null)
    try {
      await reviewApi.start(
        reviewId,
        'rev_default_human',
        reviewerName || 'Reviewer'
      )
      setSuccessMsg('Review claimed and marked IN_REVIEW.')
      await fetchDetails()
    } catch (err: unknown) {
      setError(formatApiError(err))
    } finally {
      setActionLoading(false)
    }
  }

  const handleApprove = async () => {
    setActionLoading(true)
    setError(null)
    try {
      const actionRes = await reviewApi.approve(
        reviewId,
        'rev_default_human',
        reviewerName || 'Human Reviewer',
        decisionReason || 'AI extraction approved without modification'
      )
      setSuccessMsg(actionRes.message || 'Document approved successfully!')
      setShowApproveModal(false)
      await fetchDetails()
    } catch (err: unknown) {
      setError(formatApiError(err))
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!decisionReason.trim()) {
      setError('A rejection reason is required.')
      return
    }
    setActionLoading(true)
    setError(null)
    try {
      const actionRes = await reviewApi.reject(
        reviewId,
        'rev_default_human',
        reviewerName || 'Human Reviewer',
        decisionReason
      )
      setSuccessMsg(actionRes.message || 'Document rejected.')
      setShowRejectModal(false)
      await fetchDetails()
    } catch (err: unknown) {
      setError(formatApiError(err))
    } finally {
      setActionLoading(false)
    }
  }

  const handleCorrect = async () => {
    setActionLoading(true)
    setError(null)
    try {
      const actionRes = await reviewApi.correct(
        reviewId,
        editableData,
        'rev_default_human',
        reviewerName || 'Human Reviewer',
        decisionReason || 'Manual field corrections applied'
      )
      setSuccessMsg(
        `Correction applied! Document status: ${actionRes.document_status}. Validation Score: ${
          actionRes.validation_score !== null && actionRes.validation_score !== undefined
            ? (actionRes.validation_score * 100).toFixed(0) + '%'
            : 'N/A'
        }`
      )
      setShowCorrectModal(false)
      await fetchDetails()
    } catch (err: unknown) {
      setError(formatApiError(err))
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="review-container" style={{ textAlign: 'center', padding: 'var(--space-16)' }}>
        <p style={{ color: 'var(--color-text-secondary)' }}>Loading document review details...</p>
      </div>
    )
  }

  if (!review) {
    return (
      <div className="review-container">
        <button className="btn btn-secondary" onClick={onBack}>← Back to Queue</button>
        <div className="glass-card" style={{ marginTop: '16px' }}>
          <p style={{ color: 'var(--color-accent-danger)' }}>{error || 'Review not found.'}</p>
        </div>
      </div>
    )
  }

  const doc = review.document
  const isCompleted = review.status === 'COMPLETED'
  const issues = doc.validation_result?.issues || []
  const overallConf = doc.overall_confidence ?? 0
  const valScore = doc.validation_score ?? 0

  return (
    <div className="review-container" id="review-details-view">
      {/* Header */}
      <div className="review-header">
        <div className="review-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="btn btn-secondary" onClick={onBack} title="Back to Review Queue">
              ← Queue
            </button>
            <h1>Review: {doc.original_filename}</h1>
          </div>
          <p className="review-subtitle">
            Document ID: {doc.id} • Review ID: {review.review_id}
          </p>
        </div>
        <div className="review-actions-header">
          <span className={`badge ${review.status === 'PENDING' ? 'badge-pending' : review.status === 'IN_REVIEW' ? 'badge-in_review' : 'badge-completed'}`}>
            {review.status}
          </span>
          {review.decision && (
            <span className={`badge ${review.decision === 'APPROVED' || review.decision === 'CORRECTED' ? 'badge-approved' : 'badge-rejected'}`}>
              {review.decision}
            </span>
          )}
        </div>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="glass-card" style={{ borderLeft: '4px solid var(--color-accent-success)' }}>
          <p style={{ color: 'var(--color-accent-success)', fontWeight: 500 }}>{successMsg}</p>
        </div>
      )}
      {error && (
        <div className="glass-card" style={{ borderLeft: '4px solid var(--color-accent-danger)' }}>
          <p style={{ color: 'var(--color-accent-danger)', fontWeight: 500 }}>{error}</p>
        </div>
      )}

      {/* Grid: Left Sidebar Info & Right Content */}
      <div className="review-details-grid">
        {/* Left Column: Metadata, Confidence, Issues */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {/* Document Information Card */}
          <div className="glass-card">
            <h3 className="card-title">Document Info</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: 'var(--text-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>Type:</span>
                <span className="badge badge-doc-type">{doc.document_type || 'UNKNOWN'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>Status:</span>
                <span style={{ fontWeight: 600 }}>{doc.status}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>Size:</span>
                <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>MIME:</span>
                <span>{doc.mime_type}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>Created:</span>
                <span>{new Date(review.created_at).toLocaleTimeString()}</span>
              </div>
              {review.reviewer_name && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>Reviewer:</span>
                  <span>{review.reviewer_name}</span>
                </div>
              )}
            </div>
          </div>

          {/* RAG Vector Index Status Card (Step 9 Part Q) */}
          <div className="glass-card">
            <h3 className="card-title">RAG Vector Index</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>RAG Index:</span>
                <span
                  style={{
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: 600,
                    background: doc.rag_indexed ? 'rgba(34, 197, 94, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                    color: doc.rag_indexed ? '#4ade80' : '#94a3b8',
                    border: `1px solid ${doc.rag_indexed ? 'rgba(34, 197, 94, 0.3)' : 'rgba(148, 163, 184, 0.3)'}`,
                  }}
                >
                  {doc.rag_indexed ? '✓ Indexed' : 'Not Indexed'}
                </span>
              </div>
              {doc.rag_indexed && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-secondary)' }}>Chunks:</span>
                    <span>{doc.rag_chunk_count ?? 0}</span>
                  </div>
                  {doc.rag_embedding_model && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--color-text-secondary)' }}>Model:</span>
                      <span style={{ fontFamily: 'monospace', fontSize: '11px' }}>{doc.rag_embedding_model}</span>
                    </div>
                  )}
                  {doc.rag_indexed_at && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--color-text-secondary)' }}>Indexed:</span>
                      <span>{new Date(doc.rag_indexed_at).toLocaleTimeString()}</span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Confidence Score Breakdown */}
          <div className="glass-card">
            <h3 className="card-title">Confidence Breakdown</h3>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ fontWeight: 600 }}>Overall Confidence</span>
                <span style={{ fontWeight: 700, color: overallConf >= 0.85 ? '#22c55e' : '#f5a623' }}>
                  {(overallConf * 100).toFixed(1)}%
                </span>
              </div>
              <div className="metric-bar-bg">
                <div
                  className="metric-bar-fill"
                  style={{
                    width: `${overallConf * 100}%`,
                    background: overallConf >= 0.85 ? 'var(--color-accent-success)' : 'var(--color-accent-warning)',
                  }}
                />
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                Recommendation: <strong>{doc.confidence_recommendation || 'REVIEW_REQUIRED'}</strong>
              </div>
            </div>

            <div className="metric-row">
              <span style={{ color: 'var(--color-text-secondary)' }}>Classification (25%):</span>
              <span>{((doc.classification_confidence ?? 0.85) * 100).toFixed(0)}%</span>
            </div>
            <div className="metric-row">
              <span style={{ color: 'var(--color-text-secondary)' }}>Validation Score (40%):</span>
              <span>{(valScore * 100).toFixed(0)}%</span>
            </div>
            {doc.classification_reasoning && (
              <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--color-text-secondary)', fontStyle: 'italic' }}>
                "{doc.classification_reasoning}"
              </div>
            )}
          </div>

          {/* Validation Issues Card */}
          <div className="glass-card">
            <h3 className="card-title">
              Validation Issues
              <span className="badge badge-info">{issues.length}</span>
            </h3>
            {issues.length === 0 ? (
              <p style={{ color: 'var(--color-accent-success)', fontSize: 'var(--text-sm)' }}>
                ✓ No validation issues detected.
              </p>
            ) : (
              issues.map((issue, idx) => (
                <div
                  key={idx}
                  className={`issue-card issue-card--${issue.severity.toLowerCase()}`}
                >
                  <div className="issue-header">
                    <span className="issue-field">{issue.field}</span>
                    <span className={`badge badge-${issue.severity.toLowerCase()}`}>
                      {issue.severity}
                    </span>
                  </div>
                  <div className="issue-msg">{issue.message}</div>
                  {(issue.actual_value !== undefined || issue.expected_value !== undefined) && (
                    <div className="issue-values">
                      Actual: {String(issue.actual_value)} | Expected: {String(issue.expected_value)}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* OCR Text Accordion / Box */}
          <div className="glass-card">
            <h3 className="card-title">Extracted OCR Text</h3>
            <div className="ocr-viewer" tabIndex={0} aria-label="OCR Raw Content">
              {doc.ocr_text || '(No OCR text extracted)'}
            </div>
          </div>
        </div>

        {/* Right Column: AI Extraction & Interactive Editor */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {/* AI Original vs Human Corrected Summary */}
          {review.reviewed_extracted_data && (
            <div className="glass-card" style={{ background: 'rgba(34, 197, 94, 0.05)', border: '1px solid rgba(34, 197, 94, 0.2)' }}>
              <h4 style={{ color: 'var(--color-accent-success)', marginBottom: '8px' }}>
                ✓ Human Corrections Previously Applied
              </h4>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
                Original AI extraction is safely archived in audit snapshot.
              </p>
            </div>
          )}

          {/* Editable Structured Data Editor */}
          <div className="glass-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 className="card-title" style={{ marginBottom: '2px' }}>
                  Structured Data Editor
                </h3>
                <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
                  {isCompleted
                    ? 'Review completed. Form is in read-only mode.'
                    : 'Modify fields directly below and click "Correct & Approve" to revalidate.'}
                </p>
              </div>
              <span className="badge badge-doc-type">
                Schema: {doc.document_type || 'OTHER'}
              </span>
            </div>

            <ExtractedDataEditor
              documentType={doc.document_type}
              data={editableData}
              onChange={setEditableData}
              disabled={isCompleted || actionLoading}
            />
          </div>

          {/* Review History / Timeline */}
          {review.history && review.history.length > 0 && (
            <div className="glass-card">
              <h3 className="card-title">Processing & Review History</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                {review.history.map((h) => (
                  <div
                    key={h.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '6px 0',
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 600, color: '#93c5fd' }}>{h.stage}</span>: {h.message || h.status}
                    </div>
                    <span style={{ color: 'var(--color-text-secondary)', fontSize: '11px' }}>
                      {h.completed_at ? new Date(h.completed_at).toLocaleTimeString() : 'In Progress'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sticky Bottom Action Bar */}
      {!isCompleted && (
        <div className="review-footer-bar" id="review-action-bar">
          <div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
              Current Review State: <strong style={{ color: '#fff' }}>{review.status}</strong>
            </span>
          </div>

          <div className="review-footer-actions">
            {review.status === 'PENDING' && (
              <button
                id="btn-start-review"
                className="btn btn-secondary"
                onClick={handleStartReview}
                disabled={actionLoading}
              >
                Claim & Start Review
              </button>
            )}

            <button
              id="btn-reject-review"
              className="btn btn-danger"
              onClick={() => {
                setDecisionReason('')
                setShowRejectModal(true)
              }}
              disabled={actionLoading}
            >
              Reject Document
            </button>

            <button
              id="btn-correct-approve"
              className="btn btn-primary"
              onClick={() => {
                setDecisionReason('Corrected structured fields based on source document')
                setShowCorrectModal(true)
              }}
              disabled={actionLoading}
            >
              Correct & Approve
            </button>

            <button
              id="btn-approve-review"
              className="btn btn-success"
              onClick={() => {
                setDecisionReason('AI extraction confirmed accurate')
                setShowApproveModal(true)
              }}
              disabled={actionLoading}
            >
              Approve Extraction
            </button>
          </div>
        </div>
      )}

      {/* Approve Confirmation Modal */}
      {showApproveModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal-content">
            <h3 style={{ color: 'var(--color-accent-success)' }}>Approve Document</h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
              This will approve the document extraction as-is and transition its status to APPROVED.
            </p>
            <div className="input-group">
              <label className="input-label">Reviewer Name (Optional)</label>
              <input
                type="text"
                className="input-field"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                placeholder="Reviewer name..."
              />
            </div>
            <div className="input-group">
              <label className="input-label">Decision Note (Optional)</label>
              <input
                type="text"
                className="input-field"
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                placeholder="Reason or notes..."
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowApproveModal(false)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                className="btn btn-success"
                onClick={handleApprove}
                disabled={actionLoading}
              >
                {actionLoading ? 'Approving...' : 'Confirm Approval'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Confirmation Modal */}
      {showRejectModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal-content">
            <h3 style={{ color: 'var(--color-accent-danger)' }}>Reject Document</h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
              Are you sure you want to reject this document? Please state the reason for audit purposes.
            </p>
            <div className="input-group">
              <label className="input-label">Rejection Reason *</label>
              <textarea
                rows={3}
                className="input-field"
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                placeholder="e.g. Unreadable text, missing critical supplier information..."
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowRejectModal(false)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleReject}
                disabled={actionLoading || !decisionReason.trim()}
              >
                {actionLoading ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Correct & Approve Confirmation Modal */}
      {showCorrectModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal-content">
            <h3 style={{ color: 'var(--color-accent-primary)' }}>Submit Corrections</h3>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
              Your edited fields will be validated against the <strong>{doc.document_type}</strong> schema.
              Deterministic validation and confidence will be automatically recomputed.
            </p>
            <div className="input-group">
              <label className="input-label">Correction Note</label>
              <input
                type="text"
                className="input-field"
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowCorrectModal(false)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCorrect}
                disabled={actionLoading}
              >
                {actionLoading ? 'Validating & Submitting...' : 'Apply & Validate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ReviewDetails
