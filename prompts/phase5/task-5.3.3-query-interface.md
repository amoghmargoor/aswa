# Task 5.3.3: Web Dashboard - Query Interface

## Context

You are working on the ASWA web dashboard at `/services/web-dashboard/`. Authentication is complete (Task 5.3.2). Now we need to implement the query interface.

## Objective

Create a query interface that:
1. Provides natural language query input
2. Displays answers with citations
3. Shows query history
4. Supports follow-up questions
5. Provides feedback mechanisms

## Requirements

### 1. Create `/services/web-dashboard/src/pages/Query.tsx`
```typescript
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Button, Input } from '@/components/ui';
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
```

### 2. Create `/services/web-dashboard/src/components/query/QueryInput.tsx`
```typescript
import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Button, Input } from '@/components/ui';
import { Send, Mic, Paperclip } from 'lucide-react';

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  initialValue?: string;
}

export function QueryInput({
  onSubmit,
  isLoading = false,
  placeholder = 'Ask a question...',
  initialValue = '',
}: QueryInputProps) {
  const [query, setQuery] = useState(initialValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [query]);

  const handleSubmit = () => {
    if (query.trim() && !isLoading) {
      onSubmit(query.trim());
      setQuery('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading}
        rows={1}
        className="w-full resize-none rounded-lg border border-gray-300 px-4 py-3 pr-24
                   text-gray-900 placeholder:text-gray-400
                   focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200
                   disabled:bg-gray-50 disabled:text-gray-500
                   min-h-[48px] max-h-[200px]"
      />
      <div className="absolute right-2 bottom-2 flex items-center gap-1">
        <button
          type="button"
          className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          title="Attach document"
        >
          <Paperclip className="h-5 w-5" />
        </button>
        <Button
          onClick={handleSubmit}
          disabled={!query.trim() || isLoading}
          size="sm"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
```

### 3. Create `/services/web-dashboard/src/components/query/QueryResult.tsx`
```typescript
import { useState } from 'react';
import { Card, Button } from '@/components/ui';
import { Citation } from './Citation';
import { QueryInput } from './QueryInput';
import type { QueryResponse } from '@/types';
import { ThumbsUp, ThumbsDown, RefreshCw, Copy, Check, MessageSquare } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface QueryResultProps {
  result: QueryResponse;
  onFollowUp: (query: string) => void;
  onFeedback: (type: 'helpful' | 'not_helpful') => void;
}

export function QueryResult({ result, onFollowUp, onFeedback }: QueryResultProps) {
  const [copied, setCopied] = useState(false);
  const [showFollowUp, setShowFollowUp] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<string | null>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = (type: 'helpful' | 'not_helpful') => {
    setFeedbackGiven(type);
    onFeedback(type);
  };

  const confidenceColor =
    result.confidence >= 0.7
      ? 'text-green-600'
      : result.confidence >= 0.5
      ? 'text-yellow-600'
      : 'text-red-600';

  return (
    <Card className="overflow-hidden">
      {/* Answer Section */}
      <div className="p-6">
        <div className="prose prose-sm max-w-none">
          <div className="whitespace-pre-wrap text-gray-900">
            {result.answer}
          </div>
        </div>
      </div>

      {/* Citations Section */}
      {result.citations.length > 0 && (
        <div className="border-t border-gray-100 bg-gray-50 p-4">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Sources</h4>
          <div className="space-y-2">
            {result.citations.map((citation) => (
              <Citation key={citation.index} citation={citation} />
            ))}
          </div>
        </div>
      )}

      {/* Actions Section */}
      <div className="border-t border-gray-100 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className={`text-sm ${confidenceColor}`}>
              Confidence: {(result.confidence * 100).toFixed(0)}%
            </span>
            <span className="text-sm text-gray-400">
              {result.processingTimeMs}ms
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
              title="Copy answer"
            >
              {copied ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </button>

            <button
              onClick={() => setShowFollowUp(!showFollowUp)}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
              title="Ask follow-up"
            >
              <MessageSquare className="h-4 w-4" />
            </button>

            <div className="border-l border-gray-200 pl-2 ml-2 flex items-center gap-1">
              <button
                onClick={() => handleFeedback('helpful')}
                disabled={feedbackGiven !== null}
                className={`p-2 rounded-lg ${
                  feedbackGiven === 'helpful'
                    ? 'text-green-600 bg-green-50'
                    : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                }`}
                title="Helpful"
              >
                <ThumbsUp className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleFeedback('not_helpful')}
                disabled={feedbackGiven !== null}
                className={`p-2 rounded-lg ${
                  feedbackGiven === 'not_helpful'
                    ? 'text-red-600 bg-red-50'
                    : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                }`}
                title="Not helpful"
              >
                <ThumbsDown className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Follow-up Input */}
        {showFollowUp && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <QueryInput
              onSubmit={(query) => {
                onFollowUp(query);
                setShowFollowUp(false);
              }}
              placeholder="Ask a follow-up question..."
            />
          </div>
        )}
      </div>
    </Card>
  );
}
```

### 4. Create `/services/web-dashboard/src/components/query/Citation.tsx`
```typescript
import { useState } from 'react';
import type { Citation as CitationType } from '@/types';
import { FileText, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

interface CitationProps {
  citation: CitationType;
}

export function Citation({ citation }: CitationProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-6 h-6 rounded-full bg-primary-100 text-primary-700 text-xs font-medium">
            {citation.index}
          </div>
          <FileText className="h-4 w-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-900">
            {citation.documentName}
          </span>
          {citation.pageNumber && (
            <span className="text-xs text-gray-500">
              Page {citation.pageNumber}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {(citation.relevanceScore * 100).toFixed(0)}% relevant
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="p-3 pt-0">
          <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600 border-l-4 border-primary-200">
            {citation.excerpt}
          </div>
          <div className="mt-2 flex justify-end">
            <a
              href={`/documents/${citation.documentId}`}
              className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              View document <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
```

### 5. Create `/services/web-dashboard/src/components/query/QueryHistory.tsx`
```typescript
import { Card, Button } from '@/components/ui';
import type { QueryResponse } from '@/types';
import { X, Clock, ChevronRight } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface QueryHistoryProps {
  items: QueryResponse[];
  onSelect: (query: QueryResponse) => void;
  onClose: () => void;
}

export function QueryHistory({ items, onSelect, onClose }: QueryHistoryProps) {
  if (items.length === 0) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Query History</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-gray-500 text-center py-8">No queries yet</p>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-gray-100">
        <h3 className="text-lg font-semibold">Query History</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item)}
            className="w-full text-left p-4 hover:bg-gray-50 transition-colors flex items-center justify-between group"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-900 truncate">
                {item.answer.substring(0, 100)}...
              </p>
              <div className="flex items-center gap-2 mt-1">
                <Clock className="h-3 w-3 text-gray-400" />
                <span className="text-xs text-gray-400">
                  {/* {formatDistanceToNow(new Date(item.createdAt), { addSuffix: true })} */}
                  Recently
                </span>
                <span className="text-xs text-gray-300">•</span>
                <span className="text-xs text-gray-400">
                  {item.citations.length} sources
                </span>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-gray-500" />
          </button>
        ))}
      </div>
    </Card>
  );
}
```

### 6. Create `/services/web-dashboard/src/components/query/index.ts`
```typescript
export { QueryInput } from './QueryInput';
export { QueryResult } from './QueryResult';
export { QueryHistory } from './QueryHistory';
export { Citation } from './Citation';
```

## Test Requirements

### Create `/services/web-dashboard/src/components/query/QueryInput.test.tsx`
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryInput } from './QueryInput';

describe('QueryInput', () => {
  it('renders input field', () => {
    render(<QueryInput onSubmit={() => {}} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('calls onSubmit when button clicked', () => {
    const handleSubmit = vi.fn();
    render(<QueryInput onSubmit={handleSubmit} />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Test query' } });
    fireEvent.click(screen.getByRole('button'));

    expect(handleSubmit).toHaveBeenCalledWith('Test query');
  });

  it('clears input after submit', () => {
    render(<QueryInput onSubmit={() => {}} />);

    const input = screen.getByRole('textbox') as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Test query' } });
    fireEvent.click(screen.getByRole('button'));

    expect(input.value).toBe('');
  });

  it('disables submit when loading', () => {
    render(<QueryInput onSubmit={() => {}} isLoading />);

    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Test query' } });

    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

## Verification

1. Run tests: `npm test`
2. Check query page: Navigate to `/query`
3. Test query submission
4. Verify citations display correctly
5. Test follow-up questions
