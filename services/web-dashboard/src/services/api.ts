import axios, { AxiosError, AxiosInstance } from 'axios';
import type { QueryRequest, QueryResponse, Insight, Document, DigestSummary } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('auth_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Query endpoints
  async query(request: QueryRequest): Promise<QueryResponse> {
    const { data } = await this.client.post<QueryResponse>('/query', request);
    return data;
  }

  async getQueryHistory(limit = 20): Promise<QueryResponse[]> {
    const { data } = await this.client.get<QueryResponse[]>('/query/history', {
      params: { limit },
    });
    return data;
  }

  // Insight endpoints
  async getInsights(params?: {
    type?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: Insight[]; total: number }> {
    const { data } = await this.client.get('/insights', { params });
    return data;
  }

  async getInsight(id: string): Promise<Insight> {
    const { data } = await this.client.get<Insight>(`/insights/${id}`);
    return data;
  }

  // Document endpoints
  async getDocuments(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: Document[]; total: number }> {
    const { data } = await this.client.get('/documents', { params });
    return data;
  }

  async getDocument(id: string): Promise<Document> {
    const { data } = await this.client.get<Document>(`/documents/${id}`);
    return data;
  }

  async uploadDocument(file: File): Promise<Document> {
    const formData = new FormData();
    formData.append('file', file);

    const { data } = await this.client.post<Document>('/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  }

  // Digest endpoints
  async getDigest(period: 'daily' | 'weekly' = 'daily'): Promise<DigestSummary> {
    const { data } = await this.client.get<DigestSummary>('/digest', {
      params: { period },
    });
    return data;
  }

  // Dashboard stats
  async getDashboardStats(params: {
    startDate: string;
    endDate: string;
  }): Promise<{
    totalDocuments: number;
    totalInsights: number;
    totalRisks: number;
    totalOpportunities: number;
    documentsChange: number;
    insightsChange: number;
    risksChange: number;
    opportunitiesChange: number;
    insightsTrend: Array<{ date: string; risks: number; opportunities: number; total: number }>;
    documentsChart: Array<{ name: string; count: number }>;
  }> {
    const { data } = await this.client.get('/analytics/dashboard', { params });
    return data;
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.get('/health');
      return true;
    } catch {
      return false;
    }
  }

  // Agent endpoints
  async getAgents(params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: Agent[]; total: number }> {
    const { data } = await this.client.get('/agents', { params });
    return data;
  }

  async getAgent(id: string): Promise<Agent> {
    const { data } = await this.client.get<Agent>(`/agents/${id}`);
    return data;
  }

  async createAgent(definition: AgentDefinitionPreview): Promise<Agent> {
    const { data } = await this.client.post<Agent>('/agents', definition);
    return data;
  }

  async updateAgent(id: string, updates: Partial<Agent>): Promise<Agent> {
    const { data } = await this.client.patch<Agent>(`/agents/${id}`, updates);
    return data;
  }

  async deleteAgent(id: string): Promise<void> {
    await this.client.delete(`/agents/${id}`);
  }

  async updateAgentStatus(id: string, status: 'active' | 'paused'): Promise<Agent> {
    const { data } = await this.client.post<Agent>(`/agents/${id}/status`, { status });
    return data;
  }

  async cloneAgent(id: string): Promise<Agent> {
    const { data } = await this.client.post<Agent>(`/agents/${id}/clone`);
    return data;
  }

  // Agent generation endpoints
  async startGenerationSession(input: string): Promise<GenerationSession> {
    const { data } = await this.client.post<GenerationSession>('/agents/generate/session', {
      input,
    });
    return data;
  }

  async sendGenerationMessage(sessionId: string, message: string): Promise<GenerationSession> {
    const { data } = await this.client.post<GenerationSession>(
      `/agents/generate/session/${sessionId}/message`,
      { message }
    );
    return data;
  }

  async answerClarification(
    sessionId: string,
    questionId: string,
    optionId?: string,
    customInput?: string
  ): Promise<GenerationSession> {
    const { data } = await this.client.post<GenerationSession>(
      `/agents/generate/session/${sessionId}/clarify`,
      { question_id: questionId, option_id: optionId, custom_input: customInput }
    );
    return data;
  }

  async generateAgentFromPrompt(prompt: string): Promise<AgentDefinitionPreview> {
    const { data } = await this.client.post<AgentDefinitionPreview>(
      '/agents/generate/from-prompt',
      { prompt }
    );
    return data;
  }

  async validateAgentYaml(yaml: string): Promise<{ valid: boolean; errors: string[] }> {
    const { data } = await this.client.post('/agents/validate', { yaml });
    return data;
  }

  async getAgentTemplates(): Promise<AgentTemplate[]> {
    const { data } = await this.client.get<AgentTemplate[]>('/agents/templates');
    return data;
  }
}

// Additional types for agents
interface Agent {
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

interface TriggerDefinition {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
}

interface ActionDefinition {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
  dependsOn: string[];
  order: number;
}

interface ConditionDefinition {
  id: string;
  expression: string;
  description: string;
}

interface GenerationSession {
  id: string;
  messages: ConversationMessage[];
  currentQuestions: ClarificationQuestion[];
  agentDefinition?: AgentDefinitionPreview;
  isComplete: boolean;
  confidence: number;
}

interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  questions?: ClarificationQuestion[];
  isLoading?: boolean;
}

interface ClarificationQuestion {
  id: string;
  type: string;
  question: string;
  context: string;
  options: ClarificationOption[];
  allowsCustomInput: boolean;
  relatedIntentId?: string;
  parameterName?: string;
  priority: number;
}

interface ClarificationOption {
  id: string;
  label: string;
  description: string;
  value: unknown;
  isRecommended: boolean;
}

interface AgentDefinitionPreview {
  name: string;
  displayName: string;
  trigger: TriggerDefinition;
  actions: ActionDefinition[];
  conditions: ConditionDefinition[];
  yaml: string;
  confidence: number;
}

interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  definition: AgentDefinitionPreview;
}

export const api = new ApiService();
