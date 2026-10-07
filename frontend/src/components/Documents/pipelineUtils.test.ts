import test from 'node:test'
import assert from 'node:assert/strict'
import {
  computeStageState,
  isTerminalStatus,
} from './pipelineUtils.ts'
import type { ProcessingStatusResponse } from '../../types'

test('isTerminalStatus correctly classifies terminal and non-terminal states', () => {
  // Terminal states (polling must stop)
  assert.equal(isTerminalStatus('APPROVED'), true)
  assert.equal(isTerminalStatus('AUTO_APPROVED'), true)
  assert.equal(isTerminalStatus('REVIEW_REQUIRED'), true)
  assert.equal(isTerminalStatus('REJECTED'), true)
  assert.equal(isTerminalStatus('FAILED'), true)
  assert.equal(isTerminalStatus('IN_REVIEW'), true)

  // Intermediate states (polling must continue)
  assert.equal(isTerminalStatus('UPLOADED'), false)
  assert.equal(isTerminalStatus('OCR_COMPLETED'), false)
  assert.equal(isTerminalStatus('PROCESSING'), false)
  assert.equal(isTerminalStatus('CLASSIFIED'), false)
  assert.equal(isTerminalStatus('EXTRACTED'), false)
  assert.equal(isTerminalStatus('VALIDATED'), false)
  assert.equal(isTerminalStatus('OCR_IN_PROGRESS'), false)
  assert.equal(isTerminalStatus('CLASSIFYING'), false)
  assert.equal(isTerminalStatus('EXTRACTING'), false)
  assert.equal(isTerminalStatus('VALIDATING'), false)
  assert.equal(isTerminalStatus('CONFIDENCE_CALCULATING'), false)
})

test('UPLOADED does not stop polling', () => {
  assert.equal(isTerminalStatus('UPLOADED'), false)
  assert.equal(isTerminalStatus('uploaded'), false)
})

test('OCR_COMPLETED does not stop polling', () => {
  assert.equal(isTerminalStatus('OCR_COMPLETED'), false)
  assert.equal(isTerminalStatus('ocr_completed'), false)
})

test('REVIEW_REQUIRED stops polling', () => {
  assert.equal(isTerminalStatus('REVIEW_REQUIRED'), true)
  assert.equal(isTerminalStatus('review_required'), true)
})

test('APPROVED stops polling', () => {
  assert.equal(isTerminalStatus('APPROVED'), true)
  assert.equal(isTerminalStatus('approved'), true)
  assert.equal(isTerminalStatus('AUTO_APPROVED'), true)
})

test('FAILED stops polling', () => {
  assert.equal(isTerminalStatus('FAILED'), true)
  assert.equal(isTerminalStatus('failed'), true)
  assert.equal(isTerminalStatus('REJECTED'), true)
})

test('REVIEW_REQUIRED: all pre-decision stages completed, decision is REVIEW_REQUIRED (NOT IN_PROGRESS), RAG is pending', () => {
  const statusData: ProcessingStatusResponse = {
    document_id: 'bcd16804-6a0a-44a4-94ea-8d1cc21acd0c',
    status: 'REVIEW_REQUIRED',
    current_stage: 'CONFIDENCE_SCORING',
    overall_confidence: 0.775,
    confidence_recommendation: 'REVIEW_REQUIRED',
    error_message: null,
  }

  // Pre-decision stages must all be COMPLETED
  assert.equal(computeStageState('UPLOAD', 'REVIEW_REQUIRED', statusData), 'COMPLETED')
  assert.equal(computeStageState('OCR', 'REVIEW_REQUIRED', statusData), 'COMPLETED')
  assert.equal(computeStageState('CLASSIFICATION', 'REVIEW_REQUIRED', statusData), 'COMPLETED')
  assert.equal(computeStageState('EXTRACTION', 'REVIEW_REQUIRED', statusData), 'COMPLETED')
  assert.equal(computeStageState('VALIDATION', 'REVIEW_REQUIRED', statusData), 'COMPLETED')
  assert.equal(computeStageState('CONFIDENCE', 'REVIEW_REQUIRED', statusData), 'COMPLETED')

  // Decision stage must be REVIEW_REQUIRED (terminal attention state, NOT IN_PROGRESS)
  const decisionState = computeStageState('HUMAN_REVIEW', 'REVIEW_REQUIRED', statusData)
  assert.equal(decisionState, 'REVIEW_REQUIRED')
  assert.notEqual(decisionState, 'IN_PROGRESS')

  // RAG stage must be PENDING (not indexed)
  assert.equal(computeStageState('RAG_INDEXING', 'REVIEW_REQUIRED', statusData), 'PENDING')
})

test('APPROVED: decision is COMPLETED, RAG reflects ragIndexed flag', () => {
  const statusData: ProcessingStatusResponse = {
    document_id: '84faf0f7-1246-4bff-a780-2f44b260d434',
    status: 'APPROVED',
    current_stage: 'CONFIDENCE_SCORING',
    overall_confidence: 0.8588,
    confidence_recommendation: 'AUTO_APPROVE',
    error_message: null,
  }

  assert.equal(computeStageState('UPLOAD', 'APPROVED', statusData), 'COMPLETED')
  assert.equal(computeStageState('OCR', 'APPROVED', statusData), 'COMPLETED')
  assert.equal(computeStageState('CLASSIFICATION', 'APPROVED', statusData), 'COMPLETED')
  assert.equal(computeStageState('EXTRACTION', 'APPROVED', statusData), 'COMPLETED')
  assert.equal(computeStageState('VALIDATION', 'APPROVED', statusData), 'COMPLETED')
  assert.equal(computeStageState('CONFIDENCE', 'APPROVED', statusData), 'COMPLETED')
  assert.equal(computeStageState('HUMAN_REVIEW', 'APPROVED', statusData), 'COMPLETED')

  // RAG indexing pending if ragIndexed is false
  assert.equal(computeStageState('RAG_INDEXING', 'APPROVED', statusData, false), 'PENDING')
  // RAG indexing completed if ragIndexed is true
  assert.equal(computeStageState('RAG_INDEXING', 'APPROVED', statusData, true), 'COMPLETED')
})

test('REJECTED: decision is FAILED terminal state, not running', () => {
  const statusData: ProcessingStatusResponse = {
    document_id: 'test-id',
    status: 'REJECTED',
    current_stage: 'CONFIDENCE_SCORING',
    error_message: null,
  }

  assert.equal(computeStageState('HUMAN_REVIEW', 'REJECTED', statusData), 'FAILED')
  assert.equal(computeStageState('RAG_INDEXING', 'REJECTED', statusData), 'PENDING')
})

test('FAILED: failed_stage is marked FAILED, preceding stages COMPLETED, subsequent PENDING', () => {
  const statusData: ProcessingStatusResponse = {
    document_id: 'test-id',
    status: 'FAILED',
    current_stage: 'EXTRACTION',
    failed_stage: 'EXTRACTION',
    error_message: 'Extraction timeout',
  }

  assert.equal(computeStageState('UPLOAD', 'FAILED', statusData), 'COMPLETED')
  assert.equal(computeStageState('OCR', 'FAILED', statusData), 'COMPLETED')
  assert.equal(computeStageState('CLASSIFICATION', 'FAILED', statusData), 'COMPLETED')
  assert.equal(computeStageState('EXTRACTION', 'FAILED', statusData), 'FAILED')
  assert.equal(computeStageState('VALIDATION', 'FAILED', statusData), 'PENDING')
  assert.equal(computeStageState('CONFIDENCE', 'FAILED', statusData), 'PENDING')
  assert.equal(computeStageState('HUMAN_REVIEW', 'FAILED', statusData), 'PENDING')
})

test('PROCESSING: active stage is IN_PROGRESS, preceding COMPLETED, subsequent PENDING', () => {
  const statusData: ProcessingStatusResponse = {
    document_id: 'test-id',
    status: 'PROCESSING',
    current_stage: 'EXTRACTION',
    error_message: null,
  }

  assert.equal(computeStageState('UPLOAD', 'PROCESSING', statusData), 'COMPLETED')
  assert.equal(computeStageState('OCR', 'PROCESSING', statusData), 'COMPLETED')
  assert.equal(computeStageState('CLASSIFICATION', 'PROCESSING', statusData), 'COMPLETED')
  assert.equal(computeStageState('EXTRACTION', 'PROCESSING', statusData), 'IN_PROGRESS')
  assert.equal(computeStageState('VALIDATION', 'PROCESSING', statusData), 'PENDING')
  assert.equal(computeStageState('CONFIDENCE', 'PROCESSING', statusData), 'PENDING')
  assert.equal(computeStageState('HUMAN_REVIEW', 'PROCESSING', statusData), 'PENDING')
  assert.equal(computeStageState('RAG_INDEXING', 'PROCESSING', statusData), 'PENDING')
})

test('OCR_COMPLETED: UPLOAD and OCR COMPLETED, subsequent PENDING, no active spinner', () => {
  const statusData: ProcessingStatusResponse = {
    document_id: 'test-id',
    status: 'OCR_COMPLETED',
    current_stage: 'OCR',
    error_message: null,
  }

  assert.equal(computeStageState('UPLOAD', 'OCR_COMPLETED', statusData), 'COMPLETED')
  assert.equal(computeStageState('OCR', 'OCR_COMPLETED', statusData), 'COMPLETED')
  assert.equal(computeStageState('CLASSIFICATION', 'OCR_COMPLETED', statusData), 'PENDING')
  assert.equal(computeStageState('EXTRACTION', 'OCR_COMPLETED', statusData), 'PENDING')
  assert.equal(computeStageState('VALIDATION', 'OCR_COMPLETED', statusData), 'PENDING')
  assert.equal(computeStageState('CONFIDENCE', 'OCR_COMPLETED', statusData), 'PENDING')
  assert.equal(computeStageState('HUMAN_REVIEW', 'OCR_COMPLETED', statusData), 'PENDING')
  assert.equal(computeStageState('RAG_INDEXING', 'OCR_COMPLETED', statusData), 'PENDING')
})

test('Intermediate stages (CLASSIFIED, EXTRACTED, VALIDATED) compute stages correctly', () => {
  assert.equal(computeStageState('UPLOAD', 'CLASSIFIED', null), 'COMPLETED')
  assert.equal(computeStageState('OCR', 'CLASSIFIED', null), 'COMPLETED')
  assert.equal(computeStageState('CLASSIFICATION', 'CLASSIFIED', null), 'COMPLETED')
  assert.equal(computeStageState('EXTRACTION', 'CLASSIFIED', null), 'PENDING')

  assert.equal(computeStageState('EXTRACTION', 'EXTRACTED', null), 'COMPLETED')
  assert.equal(computeStageState('VALIDATION', 'EXTRACTED', null), 'PENDING')

  assert.equal(computeStageState('VALIDATION', 'VALIDATED', null), 'COMPLETED')
  assert.equal(computeStageState('CONFIDENCE', 'VALIDATED', null), 'PENDING')
})
