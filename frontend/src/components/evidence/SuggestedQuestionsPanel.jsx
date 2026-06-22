'use client';

import { useState } from 'react';
import {
  MessageCircleQuestion,
  Sparkles,
  AlertTriangle,
  X,
  Copy,
  Check,
} from 'lucide-react';
import { generateAssessmentQuestions } from '@/lib/api/assessmentQuestions';

const BASIS_META = {
  gap: {
    label: 'Gap',
    cls: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
  },
  unclear: {
    label: 'Unclear',
    cls: 'bg-blue-500/10 text-blue-400 ring-blue-500/20',
  },
  covered: {
    label: 'Covered',
    cls: 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
  },
};

export default function SuggestedQuestionsPanel({ studentId, moduleId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [generated, setGenerated] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  const handleGenerate = async () => {
    setError('');
    setLoading(true);
    try {
      const report = await generateAssessmentQuestions(studentId, moduleId);
      const flat = [];
      (report?.questions ?? []).forEach((group) => {
        group.questions.forEach((q, i) => {
          flat.push({
            id: `${group.criterion_key}::${i}`,
            criterion_key: group.criterion_key,
            basis: group.basis,
            text: q,
          });
        });
      });
      setItems(flat);
      setGenerated(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const updateText = (id, text) =>
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, text } : it)));
  const dismiss = (id) => setItems((prev) => prev.filter((it) => it.id !== id));
  const copy = async (item) => {
    try {
      await navigator.clipboard.writeText(item.text);
      setCopiedId(item.id);
      setTimeout(() => setCopiedId(null), 1200);
    } catch {
      setError('Could not copy to clipboard.');
    }
  };

  const groups = [];
  const indexByKey = {};
  items.forEach((it) => {
    if (!(it.criterion_key in indexByKey)) {
      indexByKey[it.criterion_key] = groups.length;
      groups.push({
        criterion_key: it.criterion_key,
        basis: it.basis,
        items: [],
      });
    }
    groups[indexByKey[it.criterion_key]].items.push(it);
  });

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <MessageCircleQuestion size={14} className="text-accent" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-foreground">
            Suggested Questions
          </div>
          <div className="text-[11px] text-muted-foreground">
            {generated
              ? 'Questions to ask the student, focused on gaps and unclear areas'
              : 'Generate questions to ask the student during the assessment'}
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="w-3.5 h-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
          ) : (
            <Sparkles size={13} />
          )}
          {loading
            ? 'Generating…'
            : generated
              ? 'Regenerate'
              : 'Generate questions'}
        </button>
      </div>

      <div className="p-4 space-y-3">
        {error && (
          <div className="flex items-start gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2">
            <AlertTriangle size={12} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-[11px] text-red-400 leading-relaxed">{error}</p>
          </div>
        )}

        {!generated && !loading ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <MessageCircleQuestion
              size={18}
              className="text-muted-foreground mx-auto mb-2"
            />
            <p className="text-sm font-medium text-foreground">
              No questions yet
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Run AI matching first, then generate questions targeting the
              uncovered and unclear criteria.
            </p>
          </div>
        ) : generated && groups.length === 0 ? (
          <p className="text-[11px] text-muted-foreground leading-relaxed px-1">
            No questions remaining.
          </p>
        ) : (
          groups.map((g) => (
            <div
              key={g.criterion_key}
              className="rounded-lg border border-border overflow-hidden"
            >
              <div className="flex items-center gap-2 px-4 py-2.5 bg-secondary/40 border-b border-border">
                <span className="flex-1 text-xs font-medium text-foreground leading-snug">
                  {g.criterion_key}
                </span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ring-1 shrink-0 ${BASIS_META[g.basis]?.cls ?? ''}`}
                >
                  {BASIS_META[g.basis]?.label ?? g.basis}
                </span>
              </div>
              <div className="p-3 space-y-2">
                {g.items.map((it) => (
                  <div key={it.id} className="flex items-start gap-2">
                    <textarea
                      value={it.text}
                      onChange={(e) => updateText(it.id, e.target.value)}
                      rows={2}
                      className="flex-1 resize-none bg-background border border-border rounded-md px-3 py-2 text-[11px] text-foreground leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                    />
                    <button
                      onClick={() => copy(it)}
                      title="Copy"
                      className="shrink-0 mt-0.5 p-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
                    >
                      {copiedId === it.id ? (
                        <Check size={12} className="text-emerald-400" />
                      ) : (
                        <Copy size={12} />
                      )}
                    </button>
                    <button
                      onClick={() => dismiss(it.id)}
                      title="Dismiss"
                      className="shrink-0 mt-0.5 p-1.5 rounded-md border border-border text-muted-foreground hover:text-red-400 hover:border-red-500/30 transition-colors cursor-pointer"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
