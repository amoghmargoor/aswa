import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Button } from '@/components/ui';
import { Send, Paperclip } from 'lucide-react';

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
