import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button } from '@/components/ui';
import { QueryInput } from '@/components/query/QueryInput';
import { QueryResult } from '@/components/query/QueryResult';
import { QueryHistory } from '@/components/query/QueryHistory';
import { api } from '@/services/api';
import type { QueryResponse } from '@/types';
import { Loader2, History, Search } from 'lucide-react';

export default function Query() {
  const queryClient = useQueryClient();
  const [showHistory, setShowHistory] = useState(false);
  const [currentResult, setCurrentResult] = useState<QueryResponse | null>(null);

  const queryMutation = useMutation({
    mutationFn: (query: string) => api.query({ query }),
    onSuccess: (data) => {
      setCurrentResult(data);
      queryClient.invalidateQueries({ queryKey: ['queryHistory'] });
    },
  });

  const { data: history } = useQuery({
    queryKey: ['queryHistory'],
    queryFn: () => api.getQueryHistory(10),
    enabled: showHistory,
  });

  const handleQuery = (query: string) => {
    queryMutation.mutate(query);
  };

  const handleHistorySelect = (query: QueryResponse) => {
    setCurrentResult(query);
    setShowHistory(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Ask ASWA</h1>
          <p className="text-gray-500">Ask questions about your documents</p>
        </div>
        <Button
          variant="outline"
          onClick={() => setShowHistory(!showHistory)}
        >
          <History className="h-4 w-4 mr-2" />
          History
        </Button>
      </div>

      {showHistory && history && (
        <QueryHistory
          items={history}
          onSelect={handleHistorySelect}
          onClose={() => setShowHistory(false)}
        />
      )}

      <Card className="p-6">
        <QueryInput
          onSubmit={handleQuery}
          isLoading={queryMutation.isPending}
          placeholder="What would you like to know?"
        />
      </Card>

      {queryMutation.isPending && (
        <Card className="p-8">
          <div className="flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600 mb-4" />
            <p className="text-gray-600">Analyzing your question...</p>
          </div>
        </Card>
      )}

      {queryMutation.error && (
        <Card className="p-6 border-red-200 bg-red-50">
          <p className="text-red-700">
            Failed to process your query. Please try again.
          </p>
        </Card>
      )}

      {currentResult && !queryMutation.isPending && (
        <QueryResult
          result={currentResult}
          onFollowUp={handleQuery}
          onFeedback={(type) => {
            console.log('Feedback:', type, currentResult.id);
          }}
        />
      )}

      {!currentResult && !queryMutation.isPending && (
        <div className="text-center py-12">
          <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">
            Enter a question above to search your documents
          </p>
          <p className="text-sm text-gray-400 mt-2">
            Try: "What are the main risks in the Q4 report?"
          </p>
        </div>
      )}
    </div>
  );
}
