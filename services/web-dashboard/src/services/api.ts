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
}

export const api = new ApiService();
