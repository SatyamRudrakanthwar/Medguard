export type ReviewStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'blocked'
export type SeverityLevel = 'low' | 'moderate' | 'high' | 'critical'
export type FindingType =
  | 'drug_interaction'
  | 'contraindication'
  | 'adverse_effect'
  | 'warning'
  | 'general_information'

export interface EvidenceSource {
  source: string
  source_id?: string
  url?: string
  support_score: number
  excerpt?: string
}

export interface SafetyFinding {
  finding_id: string
  finding_type: FindingType
  title: string
  description: string
  severity: SeverityLevel
  medications_involved: string[]
  evidence: EvidenceSource[]
  confidence: number
  is_validated: boolean
  requires_professional_review: boolean
}

export interface ReviewRequest {
  age: number
  conditions: string[]
  medications: string[]
  question: string
}

export interface ReviewResponse {
  review_id: string
  status: ReviewStatus
  message?: string
  medications_reviewed: string[]
  findings: SafetyFinding[]
  evidence: EvidenceSource[]
  additional_information: string[]
  high_severity_count: number
  created_at: string
  completed_at?: string
  disclaimer: string
}

export interface StreamEvent {
  event: 'step_completed' | 'done' | 'error'
  step?: string
  message?: string
  data?: Record<string, unknown>
  timestamp: string
}
