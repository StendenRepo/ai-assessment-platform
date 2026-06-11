'use client';

import { useEffect, useRef, useState } from 'react';
import { Bot, Loader2, MessageSquare, Send } from 'lucide-react';
import {
  getAssessmentChat,
  postAssessmentChat,
} from '@/lib/api/assessmentsApi';

export default function AssessmentChatWidget({
  assessmentId,
  disabled = false,
  canChat = true,
  onDraftUpdated,
}) {
  const chatDisabled = disabled || !canChat;
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!assessmentId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getAssessmentChat(assessmentId);
        if (!cancelled) setMessages(data);
      } catch (e) {
        if (!cancelled) setError(e.message || 'Could not load chat');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending || chatDisabled) return;
    setSending(true);
    setError(null);
    setInput('');
    try {
      const res = await postAssessmentChat(assessmentId, text);
      setMessages(res.messages);
      onDraftUpdated?.(res.draft);
    } catch (err) {
      setError(err.message || 'Chat failed');
      setInput(text);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden flex flex-col max-h-[520px]">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border shrink-0">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
          <MessageSquare size={14} className="text-accent" />
        </div>
        <div>
          <div className="text-sm font-semibold text-foreground">
            Refine with AI
          </div>
          <div className="text-[11px] text-muted-foreground">
            Chat adjusts analysis only — evidence stays unchanged
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px]">
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="animate-spin text-muted-foreground" size={20} />
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-8 px-4">
            <Bot size={28} className="mx-auto text-muted-foreground mb-2" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              Ask the AI to clarify a score, add nuance, or focus on specific
              evidence. Refinements stay grounded in uploaded files.
            </p>
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.role === 'teacher' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[90%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                  m.role === 'teacher'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary border border-border text-foreground'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p className="px-4 pb-2 text-xs text-red-400">{error}</p>
      )}

      <form
        onSubmit={handleSend}
        className="border-t border-border p-3 flex gap-2 shrink-0"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={chatDisabled || sending}
          placeholder={
            disabled
              ? 'Assessment finalized — chat locked'
              : !canChat
                ? 'Generate AI suggestions first…'
                : 'e.g. Raise testing score — they added integration tests…'
          }
          className="flex-1 bg-secondary border border-border rounded-md px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={chatDisabled || sending || !input.trim()}
          className="px-3 py-2 rounded-md bg-primary text-primary-foreground disabled:opacity-40 hover:bg-primary/90 transition-colors"
        >
          {sending ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Send size={14} />
          )}
        </button>
      </form>
    </div>
  );
}
