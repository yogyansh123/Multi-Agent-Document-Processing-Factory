import type { ProcessingStatusResponse } from '../../types'

export type StageState =
  | 'COMPLETED'
  | 'IN_PROGRESS'
  | 'FAILED'
  | 'PENDING'
  | 'SKIPPED'
  | 'REVIEW_REQUIRED'

export interface PipelineStageDef {
  key: string
  label: string
}

export const STAGES: PipelineStageDef[] = [
  { key: 'UPLOAD', label: 'Upload' },
  { key: 'OCR', label: 'OCR' },
  { key: 'CLASSIFICATION', label: 'Classify' },
  { key: 'EXTRACTION', label: 'Extract' },
  { key: 'VALIDATION', label: 'Validate' },
  { key: 'CONFIDENCE', label: 'Confidence' },
  { key: 'HUMAN_REVIEW', label: 'Decision' },
  { key: 'RAG_INDEXING', label: 'RAG' },
]

export const isTerminalStatus = (status: string): boolean => {
  const s = (status || '').toUpperCase()
  return (
    s === 'AUTO_APPROVED' ||
    s === 'APPROVED' ||
    s === 'REJECTED' ||
    s === 'FAILED' ||
    s === 'REVIEW_REQUIRED' ||
    s === 'IN_REVIEW'
  )
}

export const computeStageState = (
  stageKey: string,
  currentStatus: string,
  statusData: ProcessingStatusResponse | null,
  ragIndexed?: boolean
): StageState => {
  if (statusData?.stage_statuses && statusData.stage_statuses[stageKey]) {
    return statusData.stage_statuses[stageKey] as StageState
  }

  const norm = (statusData?.status || currentStatus || '').toUpperCase()

  // 1. Terminal State: APPROVED / AUTO_APPROVED
  if (norm === 'APPROVED' || norm === 'AUTO_APPROVED') {
    if (stageKey === 'RAG_INDEXING') {
      return ragIndexed ? 'COMPLETED' : 'PENDING'
    }
    return 'COMPLETED'
  }

  // 2. Terminal State: REVIEW_REQUIRED / IN_REVIEW
  if (norm === 'REVIEW_REQUIRED' || norm === 'IN_REVIEW') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION', 'EXTRACTION', 'VALIDATION', 'CONFIDENCE'].includes(stageKey)) {
      return 'COMPLETED'
    }
    if (stageKey === 'HUMAN_REVIEW') {
      return 'REVIEW_REQUIRED'
    }
    if (stageKey === 'RAG_INDEXING') {
      return 'PENDING'
    }
  }

  // 3. Terminal State: REJECTED
  if (norm === 'REJECTED') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION', 'EXTRACTION', 'VALIDATION', 'CONFIDENCE'].includes(stageKey)) {
      return 'COMPLETED'
    }
    if (stageKey === 'HUMAN_REVIEW') {
      return 'FAILED'
    }
    if (stageKey === 'RAG_INDEXING') {
      return 'PENDING'
    }
  }

  // 4. Terminal State: FAILED
  if (norm === 'FAILED') {
    const failedStage = (statusData?.failed_stage || '').toUpperCase()
    const stageOrder = [
      'UPLOAD',
      'OCR',
      'CLASSIFICATION',
      'EXTRACTION',
      'VALIDATION',
      'CONFIDENCE',
      'HUMAN_REVIEW',
      'RAG_INDEXING',
    ]
    const stageMap: Record<string, string> = {
      UPLOAD: 'UPLOAD',
      OCR: 'OCR',
      CLASSIFICATION: 'CLASSIFICATION',
      EXTRACTION: 'EXTRACTION',
      VALIDATION: 'VALIDATION',
      CONFIDENCE_SCORING: 'CONFIDENCE',
      CONFIDENCE: 'CONFIDENCE',
      HUMAN_REVIEW: 'HUMAN_REVIEW',
      RAG_INDEXING: 'RAG_INDEXING',
    }
    const targetFailedKey = stageMap[failedStage] || 'UPLOAD'
    const failedIdx = stageOrder.indexOf(targetFailedKey)
    const thisIdx = stageOrder.indexOf(stageKey)

    if (thisIdx < failedIdx) return 'COMPLETED'
    if (thisIdx === failedIdx) return 'FAILED'
    return 'PENDING'
  }

  // 5. Idle / Intermediate States: UPLOADED / OCR_COMPLETED / CLASSIFIED / EXTRACTED / VALIDATED
  if (norm === 'UPLOADED') {
    return stageKey === 'UPLOAD' ? 'COMPLETED' : 'PENDING'
  }
  if (norm === 'OCR_COMPLETED') {
    return (stageKey === 'UPLOAD' || stageKey === 'OCR') ? 'COMPLETED' : 'PENDING'
  }
  if (norm === 'CLASSIFIED') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION'].includes(stageKey)) return 'COMPLETED'
    return 'PENDING'
  }
  if (norm === 'EXTRACTED') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION', 'EXTRACTION'].includes(stageKey)) return 'COMPLETED'
    return 'PENDING'
  }
  if (norm === 'VALIDATED') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION', 'EXTRACTION', 'VALIDATION'].includes(stageKey)) return 'COMPLETED'
    return 'PENDING'
  }

  // 6. Active Workflow State: PROCESSING
  if (norm === 'PROCESSING') {
    const currentStage = (statusData?.current_stage || '').toUpperCase()
    const stageOrder = [
      'UPLOAD',
      'OCR',
      'CLASSIFICATION',
      'EXTRACTION',
      'VALIDATION',
      'CONFIDENCE',
      'HUMAN_REVIEW',
      'RAG_INDEXING',
    ]
    const stageMap: Record<string, string> = {
      UPLOAD: 'UPLOAD',
      OCR: 'OCR',
      CLASSIFICATION: 'CLASSIFICATION',
      EXTRACTION: 'EXTRACTION',
      VALIDATION: 'VALIDATION',
      CONFIDENCE_SCORING: 'CONFIDENCE',
      CONFIDENCE: 'CONFIDENCE',
      HUMAN_REVIEW: 'HUMAN_REVIEW',
      RAG_INDEXING: 'RAG_INDEXING',
    }
    const activeKey = stageMap[currentStage] || 'OCR'
    const activeIdx = stageOrder.indexOf(activeKey)
    const thisIdx = stageOrder.indexOf(stageKey)

    if (thisIdx < activeIdx) return 'COMPLETED'
    if (thisIdx === activeIdx) return 'IN_PROGRESS'
    return 'PENDING'
  }

  // 7. Legacy fine-grained progress states
  if (norm === 'OCR_IN_PROGRESS') {
    if (stageKey === 'UPLOAD') return 'COMPLETED'
    if (stageKey === 'OCR') return 'IN_PROGRESS'
    return 'PENDING'
  }
  if (norm === 'CLASSIFYING') {
    if (stageKey === 'UPLOAD' || stageKey === 'OCR') return 'COMPLETED'
    if (stageKey === 'CLASSIFICATION') return 'IN_PROGRESS'
    return 'PENDING'
  }
  if (norm === 'EXTRACTING') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION'].includes(stageKey)) return 'COMPLETED'
    if (stageKey === 'EXTRACTION') return 'IN_PROGRESS'
    return 'PENDING'
  }
  if (norm === 'VALIDATING') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION', 'EXTRACTION'].includes(stageKey)) return 'COMPLETED'
    if (stageKey === 'VALIDATION') return 'IN_PROGRESS'
    return 'PENDING'
  }
  if (norm === 'CONFIDENCE_CALCULATING') {
    if (['UPLOAD', 'OCR', 'CLASSIFICATION', 'EXTRACTION', 'VALIDATION'].includes(stageKey)) return 'COMPLETED'
    if (stageKey === 'CONFIDENCE') return 'IN_PROGRESS'
    return 'PENDING'
  }

  if (stageKey === 'UPLOAD') return 'COMPLETED'
  return 'PENDING'
}
