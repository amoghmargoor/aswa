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

// Agent Builder Types
export interface Agent {
  id: string;
  name: string;
  displayName: string;
  description: string;
  status: 'draft' | 'active' | 'paused' | 'error';
  trigger: TriggerDefinition;
  actions: ActionDefinition[];
  conditions: ConditionDefinition[];
  createdAt: string;
  updatedAt: string;
  lastRunAt?: string;
  runCount: number;
  version: number;
}

export interface TriggerDefinition {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
}

export interface ActionDefinition {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
  dependsOn: string[];
  order: number;
}

export interface ConditionDefinition {
  id: string;
  expression: string;
  description: string;
}

export interface ClarificationQuestion {
  id: string;
  type: 'missing_trigger' | 'missing_action' | 'ambiguous_target' | 'missing_parameter' | 'multiple_options' | 'confirmation';
  question: string;
  context: string;
  options: ClarificationOption[];
  allowsCustomInput: boolean;
  relatedIntentId?: string;
  parameterName?: string;
  priority: number;
}

export interface ClarificationOption {
  id: string;
  label: string;
  description: string;
  value: unknown;
  isRecommended: boolean;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  questions?: ClarificationQuestion[];
  isLoading?: boolean;
}

export interface GenerationSession {
  id: string;
  messages: ConversationMessage[];
  currentQuestions: ClarificationQuestion[];
  agentDefinition?: AgentDefinitionPreview;
  isComplete: boolean;
  confidence: number;
}

export interface AgentDefinitionPreview {
  name: string;
  displayName: string;
  trigger: TriggerDefinition;
  actions: ActionDefinition[];
  conditions: ConditionDefinition[];
  yaml: string;
  confidence: number;
}
