import { useState } from 'react';
import { Card } from '@/components/ui';
import { Citation } from './Citation';
import { QueryInput } from './QueryInput';
import type { QueryResponse } from '@/types';
import { ThumbsUp, ThumbsDown, Copy, Check, MessageSquare } from 'lucide-react';

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
