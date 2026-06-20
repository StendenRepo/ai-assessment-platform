'use client';

import {
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  forwardRef,
} from 'react';
import {
  Bot,
  Loader2,
  MessageSquare,
  Send,
  Sparkles,
  Undo2,
} from 'lucide-react';
import {
  getAssessmentChat,
  postAssessmentChat,
  postAssessmentChatApply,
  postAssessmentChatRefine,
  postAssessmentChatReject,
  postAssessmentChatUndo,
} from '@/lib/api/assessmentsApi';
import RefineProposalCard from './RefineProposalCard';

const STARTER_CHIPS = [
  'Why is this score what it is?',
  'What evidence is weakest?',
  'Compare to rubric expectations',
  'Summarize strengths and gaps',
];

function TypingDots() {
  return (
    <div className="flex justify-start">
      <div className="bg-secondary border border-border rounded-lg px-3 py-2.5 flex items-center gap-1">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="w-1.5 h-1.5 rounded-full bg-muted-foreground/70 animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

const AssessmentChatWidget = forwardRef(function AssessmentChatWidget(
  {
    assessmentId,
    disabled = false,
    canChat = true,
    onDraftUpdated,
    onApplied,
    focusCriterionKey = null,
  },
  ref
) {
  const chatDisabled = disabled || !canChat;
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [refining, setRefining] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [error, setError] = useState(null);
  const [activeCriterionKey, setActiveCriterionKey] = useState(null);
  const [typing, setTyping] = useState({ id: null, text: '' });
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const seenIdsRef = useRef(new Set());

  useEffect(() => {
    if (!assessmentId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getAssessmentChat(assessmentId);
        if (!cancelled) {
          // Existing history loads instantly; only brand-new replies animate.
          seenIdsRef.current = new Set((data || []).map((m) => m.id));
          setMessages(data);
        }
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

  // Reveal newly-arrived AI text replies character-by-character.
  useEffect(() => {
    if (loading) return;
    const last = messages[messages.length - 1];
    if (!last || seenIdsRef.current.has(last.id)) return;
    seenIdsRef.current.add(last.id);

    if (last.role === 'teacher' || last.metadata?.type === 'proposal') return;

    const full = last.content || '';
    if (!full) return;

    setTyping({ id: last.id, text: '' });
    let i = 0;
    const step = Math.max(2, Math.ceil(full.length / 140));
    const interval = setInterval(() => {
      i += step;
      if (i >= full.length) {
        setTyping({ id: last.id, text: full });
        clearInterval(interval);
      } else {
        setTyping({ id: last.id, text: full.slice(0, i) });
      }
    }, 16);
    return () => clearInterval(interval);
  }, [messages, loading]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  useImperativeHandle(ref, () => ({
    focusCriterion(criterionKey, criterionName, score) {
      setActiveCriterionKey(criterionKey);
      const prefix = criterionName
        ? `Let's discuss ${criterionName}${score != null ? ` (currently ${score}/10)` : ''}: `
        : '';
      setInput(prefix);
      inputRef.current?.focus();
    },
  }));

  async function handleSend(e, overrideText) {
    e?.preventDefault?.();
    const text = (overrideText ?? input).trim();
    if (!text || sending || chatDisabled) return;
    setSending(true);
    setError(null);
    if (!overrideText) setInput('');
    try {
      const res = await postAssessmentChat(assessmentId, text, {
        criterionKey: activeCriterionKey || focusCriterionKey || undefined,
      });
      setMessages(res.messages);
    } catch (err) {
      setError(err.message || 'Chat failed');
      if (!overrideText) setInput(text);
    } finally {
      setSending(false);
    }
  }

  async function handleRefine() {
    if (refining || chatDisabled) return;
    setRefining(true);
    setError(null);
    try {
      const res = await postAssessmentChatRefine(assessmentId);
      setMessages(res.messages);
    } catch (err) {
      setError(err.message || 'Refine failed');
    } finally {
      setRefining(false);
    }
  }

  async function handleAccept(proposalId) {
    setAccepting(true);
    setError(null);
    try {
      const res = await postAssessmentChatApply(assessmentId, proposalId);
      setMessages(res.messages);
      onDraftUpdated?.(res.draft);
      onApplied?.(res.changes_applied || []);
    } catch (err) {
      setError(err.message || 'Could not apply proposal');
    } finally {
      setAccepting(false);
    }
  }

  async function handleReject(proposalId) {
    setRejecting(true);
    setError(null);
    try {
      const msgs = await postAssessmentChatReject(assessmentId, proposalId);
      setMessages(msgs);
    } catch (err) {
      setError(err.message || 'Could not reject proposal');
    } finally {
      setRejecting(false);
    }
  }

  async function handleUndo() {
    setUndoing(true);
    setError(null);
    try {
      const res = await postAssessmentChatUndo(assessmentId);
      setMessages(res.messages);
      onDraftUpdated?.(res.draft);
      onApplied?.(res.changes_restored || []);
    } catch (err) {
      setError(err.message || 'Nothing to undo');
    } finally {
      setUndoing(false);
    }
  }

  const hasTeacherMessage = messages.some((m) => m.role === 'teacher');
  const hasPendingProposal = messages.some(
    (m) => m.metadata?.type === 'proposal' && m.metadata?.status === 'pending'
  );

  function renderMessage(m) {
    if (m.metadata?.type === 'proposal') {
      return (
        <div key={m.id} className="flex justify-start">
          <div className="max-w-[95%] w-full">
            <RefineProposalCard
              proposal={m}
              onAccept={handleAccept}
              onReject={handleReject}
              accepting={accepting}
              rejecting={rejecting}
              disabled={chatDisabled}
            />
          </div>
        </div>
      );
    }

    const isAnimating = typing.id === m.id && typing.text !== m.content;
    const displayed = isAnimating ? typing.text : m.content;

    return (
      <div
        key={m.id}
        className={`flex ${m.role === 'teacher' ? 'justify-end' : 'justify-start'}`}
      >
        <div
          className={`max-w-[90%] rounded-lg px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
            m.role === 'teacher'
              ? 'bg-primary text-primary-foreground'
              : 'bg-secondary border border-border text-foreground'
          }`}
        >
          {displayed}
          {isAnimating && (
            <span className="inline-block w-1.5 h-3 ml-0.5 -mb-0.5 bg-current opacity-70 animate-pulse" />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden flex flex-col max-h-[560px]">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border shrink-0">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
          <MessageSquare size={14} className="text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">
            Discuss with AI
          </div>
          <div className="text-[11px] text-muted-foreground">
            Discuss this assessment — refine when ready
          </div>
        </div>
        {!chatDisabled && (
          <button
            type="button"
            onClick={handleUndo}
            disabled={undoing}
            title="Undo last applied refinement"
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-40"
          >
            {undoing ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Undo2 size={14} />
            )}
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[180px]">
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="animate-spin text-muted-foreground" size={20} />
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-6 px-4 space-y-3">
            <Bot size={28} className="mx-auto text-muted-foreground" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              Ask questions, debate scores, or explore evidence. When you are
              ready, click Refine to turn the discussion into proposed changes.
            </p>
            {!chatDisabled && (
              <div className="flex flex-wrap gap-1.5 justify-center">
                {STARTER_CHIPS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => handleSend(null, chip)}
                    disabled={sending}
                    className="text-[10px] px-2.5 py-1 rounded-full border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map(renderMessage)
        )}
        {(sending || refining) && <TypingDots />}
        <div ref={bottomRef} />
      </div>

      {error && <p className="px-4 pb-2 text-xs text-red-400">{error}</p>}

      {!chatDisabled && hasTeacherMessage && !hasPendingProposal && (
        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={handleRefine}
            disabled={refining || sending}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md bg-accent/15 text-accent text-xs font-semibold hover:bg-accent/25 transition-colors disabled:opacity-50"
          >
            {refining ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            {refining
              ? 'Generating proposal…'
              : 'Refine assessment from discussion'}
          </button>
        </div>
      )}

      <form
        onSubmit={handleSend}
        className="border-t border-border p-3 flex gap-2 shrink-0"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={chatDisabled || sending}
          placeholder={
            disabled
              ? 'Assessment finalized — chat locked'
              : !canChat
                ? 'Generate AI suggestions first…'
                : 'Ask about scores, evidence, or rubric…'
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
});

export default AssessmentChatWidget;
