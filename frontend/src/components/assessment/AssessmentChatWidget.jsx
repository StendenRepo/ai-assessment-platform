'use client';

import { useEffect, useRef, useState } from 'react';
import { Bot, Loader2, MessageCircle, Send, X } from 'lucide-react';
import { platformApi } from '@/lib/platformApi';

export default function AssessmentChatWidget({
  projectId,
  groupId,
  studentId,
  studentName,
}) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    platformApi
      .chatHistory(projectId, groupId, studentId)
      .then((msgs) => setMessages(msgs.map((m) => ({ ...m, status: 'done' }))))
      .catch(() => setMessages([]));
  }, [projectId, groupId, studentId, open]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open]);

  const send = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    const tempId = `pending-${Date.now()}`;
    setInput('');
    setSending(true);
    setMessages((c) => [
      ...c,
      { id: tempId, user: text, assistant: '', status: 'thinking' },
    ]);
    try {
      await platformApi.chatStream(projectId, groupId, studentId, text, {
        onToken: (token) => {
          setMessages((c) =>
            c.map((m) =>
              m.id === tempId
                ? {
                    ...m,
                    status: 'streaming',
                    assistant: `${m.assistant || ''}${token}`,
                  }
                : m
            )
          );
        },
        onDone: (entry) => {
          setMessages((c) =>
            c.map((m) => (m.id === tempId ? { ...entry, status: 'done' } : m))
          );
        },
        onError: (msg) => {
          setMessages((c) =>
            c.map((m) =>
              m.id === tempId
                ? {
                    ...m,
                    status: 'error',
                    assistant: msg || 'Something went wrong.',
                  }
                : m
            )
          );
        },
      });
    } catch {
      /* onError handles bubble */
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed bottom-8 right-8 z-50 flex flex-col items-end gap-3 pointer-events-none">
      <div className="pointer-events-auto flex flex-col items-end gap-3">
        {open && (
          <div
            className="w-[min(calc(100vw-4rem),400px)] h-[min(70vh,520px)] flex flex-col rounded-lg border border-border bg-card shadow-2xl overflow-hidden"
            role="dialog"
            aria-label="AI assessment assistant"
          >
            <div className="flex items-center gap-3 px-5 py-4 border-b border-border shrink-0">
              <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <Bot size={14} className="text-accent" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-foreground">
                  AI assistant
                </p>
                <p className="text-[11px] text-muted-foreground truncate">
                  {studentName || 'Assessment support'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                aria-label="Close chat"
              >
                <X size={16} />
              </button>
            </div>

            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto p-4 space-y-4 bg-background"
            >
              {messages.length === 0 && (
                <div className="rounded-lg border border-border bg-secondary/30 p-6 text-center">
                  <p className="text-sm font-medium text-foreground">
                    How can I help?
                  </p>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                    Ask about evidence, criteria, or overlaps. Run group
                    analysis first for the best answers.
                  </p>
                </div>
              )}
              {messages.map((m) => (
                <div key={m.id} className="space-y-2">
                  <div className="flex justify-end">
                    <div className="max-w-[88%] text-sm text-foreground bg-primary/10 border border-primary/20 rounded-lg rounded-br-sm px-3 py-2">
                      {m.user}
                    </div>
                  </div>
                  <div className="flex justify-start">
                    {m.status === 'thinking' ? (
                      <Loader2
                        size={16}
                        className="animate-spin text-muted-foreground ml-1"
                      />
                    ) : (
                      <div
                        className={`max-w-[88%] text-sm leading-relaxed rounded-lg rounded-bl-sm px-3 py-2 border ${
                          m.status === 'error'
                            ? 'bg-red-500/10 border-red-500/20 text-red-400'
                            : 'bg-secondary border-border text-muted-foreground'
                        }`}
                      >
                        {m.assistant || '…'}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <form
              onSubmit={send}
              className="flex items-center gap-2 p-4 border-t border-border bg-card shrink-0"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message…"
                className="flex-1 h-10 bg-secondary border border-border rounded-md px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="h-10 w-10 flex items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-50 shrink-0 hover:bg-primary/90 transition-colors"
                aria-label="Send message"
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        )}

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className={`w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 active:scale-95 ${
            open
              ? 'bg-card text-foreground border border-border'
              : 'bg-primary text-primary-foreground hover:bg-primary/90'
          }`}
          aria-label={open ? 'Close AI chat' : 'Open AI chat'}
          aria-expanded={open}
        >
          {open ? <X size={22} /> : <MessageCircle size={22} />}
        </button>
      </div>
    </div>
  );
}
