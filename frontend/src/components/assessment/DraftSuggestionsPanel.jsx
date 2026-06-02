'use client';

import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { platformApi } from '@/lib/platformApi';

const fieldCls =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all resize-none';

export default function DraftSuggestionsPanel({
  projectId,
  groupId,
  studentId,
  draftForm,
  onSaved,
}) {
  const [drafts, setDrafts] = useState(draftForm || []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setDrafts(draftForm || []);
  }, [draftForm]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await platformApi.updateDraft(projectId, groupId, studentId, drafts);
      onSaved?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!drafts?.length) {
    return (
      <div className="rounded-lg border border-border bg-secondary/20 px-5 py-6 text-center">
        <p className="text-sm text-muted-foreground">
          Run group analysis to generate AI draft suggestions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {drafts.map((d, i) => (
        <div
          key={d.criterion || i}
          className="rounded-lg border border-border p-5 space-y-3"
        >
          <div className="flex items-start justify-between gap-3">
            <h4 className="text-sm font-semibold text-foreground">
              {d.criterion}
            </h4>
            {d.suggestion_strength != null && (
              <span className="shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-accent/10 text-accent ring-1 ring-accent/20">
                {d.suggestion_strength}% strength
              </span>
            )}
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              AI suggestion
            </label>
            <textarea
              rows={3}
              value={d.suggestion || ''}
              onChange={(e) => {
                const next = [...drafts];
                next[i] = { ...d, suggestion: e.target.value };
                setDrafts(next);
              }}
              className={fieldCls}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Teacher comment
            </label>
            <textarea
              rows={2}
              placeholder="Optional notes for this criterion…"
              value={d.teacher_comment || ''}
              onChange={(e) => {
                const next = [...drafts];
                next[i] = { ...d, teacher_comment: e.target.value };
                setDrafts(next);
              }}
              className={fieldCls}
            />
          </div>
        </div>
      ))}
      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-2">
          {error}
        </p>
      )}
      <div className="flex justify-end pt-1">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          Save AI drafts
        </button>
      </div>
    </div>
  );
}
