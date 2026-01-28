import { useQuery as useTanstackQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/services/api';
import type { QueryRequest } from '@/types';

export function useQueryHistory(limit = 20) {
  return useTanstackQuery({
    queryKey: ['queryHistory', limit],
    queryFn: () => api.getQueryHistory(limit),
  });
}

export function useAskQuery() {
  return useMutation({
    mutationFn: (request: QueryRequest) => api.query(request),
  });
}

export function useInsights(params?: { type?: string; limit?: number; offset?: number }) {
  return useTanstackQuery({
    queryKey: ['insights', params],
    queryFn: () => api.getInsights(params),
  });
}

export function useDocuments(params?: { status?: string; limit?: number; offset?: number }) {
  return useTanstackQuery({
    queryKey: ['documents', params],
    queryFn: () => api.getDocuments(params),
  });
}

export function useDigest(period: 'daily' | 'weekly' = 'daily') {
  return useTanstackQuery({
    queryKey: ['digest', period],
    queryFn: () => api.getDigest(period),
  });
}
