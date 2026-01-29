import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sparkles, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Button, Input, Card } from '@/components/ui';
import { useAgentBuilderStore } from '@/stores/agentBuilderStore';
import { useStartSession, useSendMessage, useAnswerClarification } from '@/hooks/useAgentGeneration';
import type { ClarificationQuestion, ClarificationOption, ConversationMessage } from '@/types';

interface NLPBuilderProps {
  onComplete?: () => void;
}

export function NLPBuilder({ onComplete }: NLPBuilderProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    sessionId,
    messages,
    currentQuestions,
    isProcessing,
    agentDefinition,
    addMessage,
    updateLastMessage,
    setCurrentQuestions,
    setProcessing,
    startSession,
    setAgentDefinition,
    setStep,
  } = useAgentBuilderStore();

  const startSessionMutation = useStartSession();
  const sendMessageMutation = useSendMessage(sessionId || '');
  const answerClarificationMutation = useAnswerClarification(sessionId || '');

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!input.trim() || isProcessing) return;

    const userMessage = input.trim();
    setInput('');
    setProcessing(true);

    // Add user message
    addMessage({ role: 'user', content: userMessage });

    // Add loading assistant message
    addMessage({ role: 'assistant', content: '', isLoading: true });

    try {
      if (!sessionId) {
        // Start new session
        const session = await startSessionMutation.mutateAsync(userMessage);
        startSession(session.id);

        updateLastMessage({
          content: session.messages[session.messages.length - 1]?.content || '',
          isLoading: false,
          questions: session.currentQuestions,
        });

        setCurrentQuestions(session.currentQuestions);

        if (session.agentDefinition) {
          setAgentDefinition(session.agentDefinition);
        }

        if (session.isComplete) {
          setStep('review');
          onComplete?.();
        }
      } else {
        // Continue conversation
        const session = await sendMessageMutation.mutateAsync(userMessage);

        updateLastMessage({
          content: session.messages[session.messages.length - 1]?.content || '',
          isLoading: false,
          questions: session.currentQuestions,
        });

        setCurrentQuestions(session.currentQuestions);

        if (session.agentDefinition) {
          setAgentDefinition(session.agentDefinition);
        }

        if (session.isComplete) {
          setStep('review');
          onComplete?.();
        }
      }
    } catch (error) {
      updateLastMessage({
        content: 'Sorry, something went wrong. Please try again.',
        isLoading: false,
      });
    } finally {
      setProcessing(false);
    }
  }, [input, isProcessing, sessionId, startSessionMutation, sendMessageMutation]);

  const handleOptionSelect = useCallback(
    async (question: ClarificationQuestion, option: ClarificationOption) => {
      if (!sessionId || isProcessing) return;

      setProcessing(true);
      addMessage({ role: 'user', content: option.label });
      addMessage({ role: 'assistant', content: '', isLoading: true });

      try {
        const session = await answerClarificationMutation.mutateAsync({
          questionId: question.id,
          optionId: option.id,
        });

        updateLastMessage({
          content: session.messages[session.messages.length - 1]?.content || '',
          isLoading: false,
          questions: session.currentQuestions,
        });

        setCurrentQuestions(session.currentQuestions);

        if (session.agentDefinition) {
          setAgentDefinition(session.agentDefinition);
        }

        if (session.isComplete) {
          setStep('review');
          onComplete?.();
        }
      } catch (error) {
        updateLastMessage({
          content: 'Sorry, something went wrong. Please try again.',
          isLoading: false,
        });
      } finally {
        setProcessing(false);
      }
    },
    [sessionId, isProcessing, answerClarificationMutation]
  );

  const handleCustomInput = useCallback(
    async (question: ClarificationQuestion, customValue: string) => {
      if (!sessionId || isProcessing || !customValue.trim()) return;

      setProcessing(true);
      addMessage({ role: 'user', content: customValue });
      addMessage({ role: 'assistant', content: '', isLoading: true });

      try {
        const session = await answerClarificationMutation.mutateAsync({
          questionId: question.id,
          customInput: customValue,
        });

        updateLastMessage({
          content: session.messages[session.messages.length - 1]?.content || '',
          isLoading: false,
          questions: session.currentQuestions,
        });

        setCurrentQuestions(session.currentQuestions);

        if (session.agentDefinition) {
          setAgentDefinition(session.agentDefinition);
        }

        if (session.isComplete) {
          setStep('review');
          onComplete?.();
        }
      } catch (error) {
        updateLastMessage({
          content: 'Sorry, something went wrong. Please try again.',
          isLoading: false,
        });
      } finally {
        setProcessing(false);
      }
    },
    [sessionId, isProcessing, answerClarificationMutation]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-gray-200">
        <div className="p-2 bg-primary-100 rounded-lg">
          <Sparkles className="w-5 h-5 text-primary-600" />
        </div>
        <div>
          <h2 className="font-semibold text-gray-900">AI Agent Builder</h2>
          <p className="text-sm text-gray-500">Describe what you want your agent to do</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <Sparkles className="w-12 h-12 text-primary-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              Create Your AI Agent
            </h3>
            <p className="text-gray-500 max-w-md mx-auto mb-6">
              Describe what you want your agent to do in natural language. For example:
            </p>
            <div className="space-y-2 text-sm text-gray-600">
              <ExamplePrompt text="When I get an email, summarize it and send to Slack" />
              <ExamplePrompt text="Notify me when a critical risk is detected in documents" />
              <ExamplePrompt text="Create a weekly digest of all new insights" />
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onOptionSelect={handleOptionSelect}
            onCustomInput={handleCustomInput}
          />
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Agent Preview (if available) */}
      {agentDefinition && (
        <div className="px-4 py-2 border-t border-gray-200 bg-green-50">
          <div className="flex items-center gap-2 text-sm text-green-700">
            <CheckCircle className="w-4 h-4" />
            <span>
              Agent ready: <strong>{agentDefinition.displayName}</strong>
              {' '}({Math.round(agentDefinition.confidence * 100)}% confidence)
            </span>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
          className="flex gap-2"
        >
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what your agent should do..."
            disabled={isProcessing}
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={!input.trim() || isProcessing}
            className="px-4"
          >
            {isProcessing ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}

function ExamplePrompt({ text }: { text: string }) {
  return (
    <p className="px-4 py-2 bg-gray-50 rounded-lg inline-block">
      "{text}"
    </p>
  );
}

interface MessageBubbleProps {
  message: ConversationMessage;
  onOptionSelect: (question: ClarificationQuestion, option: ClarificationOption) => void;
  onCustomInput: (question: ClarificationQuestion, value: string) => void;
}

function MessageBubble({ message, onOptionSelect, onCustomInput }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-gray-100 text-gray-900'
        }`}
      >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap">{message.content}</p>

            {/* Clarification options */}
            {message.questions && message.questions.length > 0 && (
              <div className="mt-3 space-y-3">
                {message.questions.map((question) => (
                  <ClarificationOptions
                    key={question.id}
                    question={question}
                    onSelect={(option) => onOptionSelect(question, option)}
                    onCustomInput={(value) => onCustomInput(question, value)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

interface ClarificationOptionsProps {
  question: ClarificationQuestion;
  onSelect: (option: ClarificationOption) => void;
  onCustomInput: (value: string) => void;
}

function ClarificationOptions({ question, onSelect, onCustomInput }: ClarificationOptionsProps) {
  const [customValue, setCustomValue] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);

  return (
    <div className="bg-white rounded-lg p-3 shadow-sm">
      <p className="text-sm font-medium text-gray-700 mb-2">{question.question}</p>
      {question.context && (
        <p className="text-xs text-gray-500 mb-2">{question.context}</p>
      )}

      <div className="flex flex-wrap gap-2">
        {question.options.map((option) => (
          <button
            key={option.id}
            onClick={() => onSelect(option)}
            className={`px-3 py-1.5 text-sm rounded-full border transition-colors ${
              option.isRecommended
                ? 'border-primary-500 bg-primary-50 text-primary-700 hover:bg-primary-100'
                : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            {option.label}
            {option.isRecommended && (
              <span className="ml-1 text-xs text-primary-500">*</span>
            )}
          </button>
        ))}

        {question.allowsCustomInput && !showCustomInput && (
          <button
            onClick={() => setShowCustomInput(true)}
            className="px-3 py-1.5 text-sm rounded-full border border-dashed border-gray-300 text-gray-500 hover:bg-gray-50"
          >
            Other...
          </button>
        )}
      </div>

      {showCustomInput && question.allowsCustomInput && (
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={customValue}
            onChange={(e) => setCustomValue(e.target.value)}
            placeholder="Enter custom value..."
            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && customValue.trim()) {
                onCustomInput(customValue);
              }
            }}
          />
          <button
            onClick={() => customValue.trim() && onCustomInput(customValue)}
            disabled={!customValue.trim()}
            className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            Submit
          </button>
        </div>
      )}
    </div>
  );
}

export default NLPBuilder;
