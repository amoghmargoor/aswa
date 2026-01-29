import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import type {
  Agent,
  AgentDefinitionPreview,
  ClarificationQuestion,
  GenerationSession,
} from '@/types';

// Query keys
export const agentKeys = {
  all: ['agents'] as const,
  lists: () => [...agentKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) =>
    [...agentKeys.lists(), filters] as const,
  details: () => [...agentKeys.all, 'detail'] as const,
  detail: (id: string) => [...agentKeys.details(), id] as const,
  session: (id: string) => [...agentKeys.all, 'session', id] as const,
};

// List agents
export function useAgents(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: agentKeys.list(params || {}),
    queryFn: () => api.getAgents(params),
  });
}

// Get single agent
export function useAgent(id: string) {
  return useQuery({
    queryKey: agentKeys.detail(id),
    queryFn: () => api.getAgent(id),
    enabled: !!id,
  });
}

// Start generation session
export function useStartSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: string) => api.startGenerationSession(input),
    onSuccess: (data) => {
      queryClient.setQueryData(agentKeys.session(data.id), data);
    },
  });
}

// Send message in session
export function useSendMessage(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (message: string) =>
      api.sendGenerationMessage(sessionId, message),
    onSuccess: (data) => {
      queryClient.setQueryData(agentKeys.session(sessionId), data);
    },
  });
}

// Answer clarification question
export function useAnswerClarification(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      questionId,
      optionId,
      customInput,
    }: {
      questionId: string;
      optionId?: string;
      customInput?: string;
    }) => api.answerClarification(sessionId, questionId, optionId, customInput),
    onSuccess: (data) => {
      queryClient.setQueryData(agentKeys.session(sessionId), data);
    },
  });
}

// Generate from single prompt (non-conversational)
export function useGenerateFromPrompt() {
  return useMutation({
    mutationFn: (prompt: string) => api.generateAgentFromPrompt(prompt),
  });
}

// Create agent from definition
export function useCreateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (definition: AgentDefinitionPreview) =>
      api.createAgent(definition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });
    },
  });
}

// Update agent
export function useUpdateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<Agent> }) =>
      api.updateAgent(id, updates),
    onSuccess: (data) => {
      queryClient.setQueryData(agentKeys.detail(data.id), data);
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });
    },
  });
}

// Delete agent
export function useDeleteAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteAgent(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: agentKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });
    },
  });
}

// Activate/pause agent
export function useToggleAgentStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'active' | 'paused' }) =>
      api.updateAgentStatus(id, status),
    onSuccess: (data) => {
      queryClient.setQueryData(agentKeys.detail(data.id), data);
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });
    },
  });
}

// Validate YAML
export function useValidateYaml() {
  return useMutation({
    mutationFn: (yaml: string) => api.validateAgentYaml(yaml),
  });
}

// Get agent templates
export function useAgentTemplates() {
  return useQuery({
    queryKey: ['agent-templates'],
    queryFn: () => api.getAgentTemplates(),
  });
}

// Clone agent
export function useCloneAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.cloneAgent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentKeys.lists() });
    },
  });
}
