import { Card } from '@/components/ui';
import type { QueryResponse } from '@/types';
import { X, Clock, ChevronRight } from 'lucide-react';

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
