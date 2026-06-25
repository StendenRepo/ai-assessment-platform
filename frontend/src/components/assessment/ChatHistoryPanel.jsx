'use client';

import { useEffect, useState } from 'react';
import { Bot, Loader2, MessageSquare } from 'lucide-react';
import { getAssessmentChat } from '@/lib/api/assessmentsApi';
import RefineProposalCard from './RefineProposalCard';
import ChatMessageContent from './ChatMessageContent';

function formatTimestamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

// Read-only transcript of the AI conversation for an assessment. Decoupled from
// the refine workflow: no input box, no apply/reject — purely for review, and it
// works on finalized/locked assessments because GET /chat is ownership-gated only.
export default function ChatHistoryPanel({ assessmentId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!assessmentId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getAssessmentChat(assessmentId);
        if (!cancelled) setMessages(Array.isArray(data) ? data : []);
      } catch (e) {
        if (!cancelled) setError(e.message || 'Could not load chat history');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  function renderMessage(m) {
    const timestamp = formatTimestamp(m.timestamp);

    if (m.metadata?.type === 'proposal') {
      return (
        <div key={m.id} className="flex flex-col items-start gap-1">
          <div className="max-w-[95%] w-full">
            <RefineProposalCard proposal={m} disabled />
          </div>
          {timestamp && (
            <span className="text-[10px] text-muted-foreground pl-1">
              AI proposal · {timestamp}
            </span>
          )}
        </div>
      );
    }

    const isTeacher = m.role === 'teacher';

    return (
      <div
        key={m.id}
        className={`flex flex-col gap-1 ${isTeacher ? 'items-end' : 'items-start'}`}
      >
        <div
          className={`max-w-[95%] rounded-lg px-3 py-2 ${
            isTeacher
              ? 'bg-primary text-primary-foreground text-xs leading-relaxed whitespace-pre-wrap'
              : 'bg-secondary border border-border text-foreground'
          }`}
        >
          {isTeacher ? m.content : <ChatMessageContent content={m.content} />}
        </div>
        <span className="text-[10px] text-muted-foreground px-1">
          {isTeacher ? 'Teacher' : 'AI'}
          {timestamp ? ` · ${timestamp}` : ''}
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden flex flex-col max-h-[640px]">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border shrink-0">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
          <MessageSquare size={14} className="text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">
            Chat History
          </div>
          <div className="text-[11px] text-muted-foreground">
            Read-only record of the AI conversation for this assessment
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[180px]">
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="animate-spin text-muted-foreground" size={20} />
          </div>
        ) : error ? (
          <p className="px-1 py-6 text-center text-xs text-red-400">{error}</p>
        ) : messages.length === 0 ? (
          <div className="text-center py-10 px-4 space-y-2">
            <Bot size={28} className="mx-auto text-muted-foreground" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              No chat history for this assessment
            </p>
          </div>
        ) : (
          messages.map(renderMessage)
        )}
      </div>
    </div>
  );
}
