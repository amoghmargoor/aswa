export interface User {
  id: string;
  email: string;
  name: string;
  tenantId: string;
  role: 'admin' | 'user' | 'viewer';
}

export interface QueryRequest {
  query: string;
  documentIds?: string[];
  filters?: Record<string, unknown>;
}

export interface QueryResponse {
  id: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  processingTimeMs: number;
}

export interface Citation {
  index: number;
  documentId: string;
  documentName: string;
  pageNumber?: number;
  excerpt: string;
  relevanceScore: number;
}

export interface Insight {
  id: string;
  type: 'risk' | 'opportunity' | 'entity' | 'trend';
  title: string;
  description: string;
  confidence: number;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  documentId?: string;
  documentName?: string;
  createdAt: string;
}

export interface Document {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  insightCount: number;
  uploadedAt: string;
  processedAt?: string;
}

export interface DigestSummary {
  period: 'daily' | 'weekly';
  startDate: string;
  endDate: string;
  newDocuments: number;
  newInsights: number;
  topRisks: Insight[];
  topOpportunities: Insight[];
}

export interface ApiError {
  message: string;
  code: string;
  details?: Record<string, unknown>;
}
