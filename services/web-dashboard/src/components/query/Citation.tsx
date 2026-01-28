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
