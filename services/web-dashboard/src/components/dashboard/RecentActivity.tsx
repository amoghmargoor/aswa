import { Card } from '@/components/ui';
import type { Document } from '@/types';
import { FileText, CheckCircle, XCircle, Clock, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';

interface RecentActivityProps {
  documents: Document[];
}

export function RecentActivity({ documents }: RecentActivityProps) {
  const statusIcons = {
    completed: <CheckCircle className="h-4 w-4 text-green-600" />,
    failed: <XCircle className="h-4 w-4 text-red-600" />,
    processing: <Clock className="h-4 w-4 text-yellow-600 animate-pulse" />,
    pending: <Clock className="h-4 w-4 text-gray-400" />,
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Recent Documents</h3>
        <Link
          to="/documents"
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          View all <ChevronRight className="h-4 w-4" />
        </Link>
      </div>
      <div className="space-y-3">
        {documents.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No documents yet</p>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <div className="p-2 bg-gray-100 rounded-lg">
                <FileText className="h-4 w-4 text-gray-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {doc.name}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {statusIcons[doc.status]}
                  <span className="text-xs text-gray-500 capitalize">
                    {doc.status}
                  </span>
                  <span className="text-xs text-gray-300">•</span>
                  <span className="text-xs text-gray-500">
                    {formatDistanceToNow(new Date(doc.uploadedAt), { addSuffix: true })}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900">
                  {doc.insightCount}
                </p>
                <p className="text-xs text-gray-500">insights</p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
