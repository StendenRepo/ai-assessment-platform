'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  History,
  Loader2,
  Lock,
  MessageSquare,
  PenLine,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react';
import {
  finalizeAssessment,
  generateAssessmentSuggestions,
  getAssessmentDraft,
  getFinalizedAssessment,
  patchAssessmentOverrides,
  revertCriterionOverride,
} from '@/lib/api/assessmentsApi';
import HighlightedComment from './HighlightedComment';
import OverrideBadge from './OverrideBadge';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

const GRADE_OPTIONS = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F'];

export default function AssessmentFormPanel({
  assessmentId,
  moduleId,
  readOnly = false,
  onDraftChange,
  onFinalized,
  externalDraft = null,
  refreshToken = 0,
  highlightedCriteria = [],
  onDiscussCriterion,
}) {
  const [draft, setDraft] = useState(null);
  const [finalized, setFinalized] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState(null);
  const [expandedAi, setExpandedAi] = useState(null);
  const [localEdits, setLocalEdits] = useState({});
  const [localSummary, setLocalSummary] = useState('');
  const [localGrade, setLocalGrade] = useState('');
  const [teacherNotes, setTeacherNotes] = useState('');
  const [editingKeys, setEditingKeys] = useState(() => new Set());
  const [flashKeys, setFlashKeys] = useState([]);
  const criterionRefs = useRef({});

  const syncLocalFromDraft = useCallback((data) => {
    const edits = {};
    data.criteria?.forEach((c) => {
      edits[c.key] = {
        score: c.effective?.score ?? '',
        comment: c.effective?.comment ?? '',
      };
    });
    setLocalEdits(edits);
    setLocalSummary(data.summary?.effective ?? '');
    setLocalGrade(data.overall_grade?.effective ?? '');
  }, []);

  const loadDraft = useCallback(async () => {
    if (!assessmentId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getAssessmentDraft(assessmentId);
      setDraft(data);
      onDraftChange?.(data);
      syncLocalFromDraft(data);
      if (data.locked || data.status === 'final') {
        try {
          const finalData = await getFinalizedAssessment(assessmentId);
          setFinalized(finalData);
        } catch {
          setFinalized(null);
        }
      } else {
        setFinalized(null);
      }
    } catch (e) {
      setError(e.message || 'Failed to load assessment draft');
    } finally {
      setLoading(false);
    }
  }, [assessmentId, onDraftChange, syncLocalFromDraft]);

  useEffect(() => {
    loadDraft();
  }, [loadDraft]);

  useEffect(() => {
    if (!externalDraft) return;
    setDraft(externalDraft);
    syncLocalFromDraft(externalDraft);
    onDraftChange?.(externalDraft);
  }, [externalDraft, refreshToken, syncLocalFromDraft, onDraftChange]);

  useEffect(() => {
    if (!highlightedCriteria?.length) return;
    setFlashKeys(highlightedCriteria);
    const first = highlightedCriteria[0];
    const el = criterionRefs.current[first];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    const timer = setTimeout(() => setFlashKeys([]), 3000);
    return () => clearTimeout(timer);
  }, [highlightedCriteria, refreshToken]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const res = await generateAssessmentSuggestions(assessmentId);
      setDraft(res.draft);
      onDraftChange?.(res.draft);
      syncLocalFromDraft(res.draft);
      setEditingKeys(new Set());
    } catch (e) {
      setError(e.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  function buildChangedOverrides(keys) {
    return keys
      .map((key) => {
        const c = draft?.criteria?.find((x) => x.key === key);
        const edit = localEdits[key] || {};
        const eff = c?.effective || {};
        const score =
          edit.score === '' || edit.score == null ? null : parseFloat(edit.score);
        const comment = edit.comment ?? '';
        if (score === eff.score && comment === (eff.comment || '')) return null;
        return { criterion_key: key, score, comment };
      })
      .filter(Boolean);
  }

  async function saveOverrides(
    keys,
    { includeSummaryGrade = false, exitEditMode = false } = {}
  ) {
    const overrides = buildChangedOverrides(keys);
    const payload = { overrides };
    if (includeSummaryGrade) {
      if (localSummary !== (draft.summary?.effective ?? '')) {
        payload.summary = localSummary;
      }
      if (localGrade !== (draft.overall_grade?.effective ?? '')) {
        payload.overall_grade = localGrade;
      }
    }
    if (!overrides.length && !payload.summary && !payload.overall_grade) {
      if (exitEditMode) {
        setEditingKeys((prev) => {
          const next = new Set(prev);
          keys.forEach((k) => next.delete(k));
          return next;
        });
      }
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const updated = await patchAssessmentOverrides(assessmentId, payload);
      setDraft(updated);
      onDraftChange?.(updated);
      syncLocalFromDraft(updated);
      if (exitEditMode) {
        setEditingKeys((prev) => {
          const next = new Set(prev);
          keys.forEach((k) => next.delete(k));
          return next;
        });
      }
    } catch (e) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  function startEditing(key) {
    const c = draft?.criteria?.find((x) => x.key === key);
    const eff = c?.effective || {};
    setLocalEdits((prev) => ({
      ...prev,
      [key]: {
        score: eff.score ?? '',
        comment: eff.comment ?? '',
      },
    }));
    setEditingKeys((prev) => new Set(prev).add(key));
  }

  function cancelEditing(key) {
    const c = draft?.criteria?.find((x) => x.key === key);
    const eff = c?.effective || {};
    setLocalEdits((prev) => ({
      ...prev,
      [key]: {
        score: eff.score ?? '',
        comment: eff.comment ?? '',
      },
    }));
    setEditingKeys((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }

  async function handleRevert(key) {
    setSaving(true);
    try {
      const updated = await revertCriterionOverride(assessmentId, key);
      setDraft(updated);
      onDraftChange?.(updated);
      const c = updated.criteria.find((x) => x.key === key);
      setLocalEdits((prev) => ({
        ...prev,
        [key]: {
          score: c?.effective?.score ?? '',
          comment: c?.effective?.comment ?? '',
        },
      }));
      setEditingKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    } catch (e) {
      setError(e.message || 'Revert failed');
    } finally {
      setSaving(false);
    }
  }

  async function handleFinalize() {
    const confirmedOverlap =
      draft?.overlap_alerts?.some((a) => a.status === 'confirmed') ?? false;
    let msg =
      'Finalize this assessment? The form will be locked from further AI changes.';
    if (confirmedOverlap) {
      msg +=
        '\n\nNote: high-confidence overlap indicators exist for this student. Review overlaps manually before finalizing.';
    }
    if (!window.confirm(msg)) return;

    setFinalizing(true);
    setError(null);
    try {
      const finalData = await finalizeAssessment(assessmentId, { teacherNotes });
      setFinalized(finalData);
      onFinalized?.(finalData);
      await loadDraft();
    } catch (e) {
      setError(e.message || 'Finalization failed');
    } finally {
      setFinalizing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  const locked = draft?.locked || readOnly || draft?.status === 'final';
  const hasSuggestions = draft?.criteria?.some((c) => c.ai);
  const confirmedOverlaps =
    draft?.overlap_alerts?.filter((a) => a.status === 'confirmed') ?? [];

  return (
    <div className="space-y-4">
      {locked && finalized && (
        <div className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
          <Lock size={16} className="text-emerald-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground">
              Assessment finalized
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Read-only snapshot saved to the assessment record. Grade{' '}
              <span className="font-mono font-semibold text-foreground">
                {finalized.overall_grade || finalized.form?.grade || '—'}
              </span>
              {finalized.form?.finalized_at && (
                <>
                  {' '}
                  ·{' '}
                  {new Date(finalized.form.finalized_at).toLocaleString('en-GB')}
                </>
              )}
            </p>
            {finalized.form?.teacher_notes && (
              <p className="text-xs text-foreground mt-2 border-t border-border/50 pt-2">
                <span className="font-medium">Teacher notes:</span>{' '}
                {finalized.form.teacher_notes}
              </p>
            )}
          </div>
        </div>
      )}

      {locked && !finalized && draft?.status === 'final' && (
        <div className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
          <Lock size={16} className="text-emerald-400 mt-0.5 shrink-0" />
          <p className="text-sm text-muted-foreground">
            This form is read-only. Grade{' '}
            <span className="font-mono font-semibold text-foreground">
              {draft.overall_grade?.effective || '—'}
            </span>{' '}
            saved to the assessment record.
          </p>
        </div>
      )}

      {!locked && confirmedOverlaps.length > 0 && moduleId && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <AlertTriangle
            size={16}
            className="text-amber-400 mt-0.5 shrink-0"
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground">
              Overlap indicators ({confirmedOverlaps.length} high confidence)
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Review overlap signals before finalizing this assessment.
            </p>
            <Link
              href={`/modules/${moduleId}/overlaps`}
              className="text-xs text-primary hover:underline mt-1 inline-block"
            >
              Review overlaps →
            </Link>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Assessment Criteria
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {hasSuggestions
              ? 'Review AI suggestions below. Click Override on any criterion to change it.'
              : 'Generate AI suggestions from uploaded evidence first.'}
          </p>
        </div>
        {!locked && (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-accent/15 text-accent text-sm font-medium hover:bg-accent/25 transition-colors disabled:opacity-50"
          >
            {generating ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            {hasSuggestions ? 'Regenerate AI' : 'Generate AI suggestions'}
          </button>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-400 rounded-md bg-red-500/10 px-3 py-2">
          {error}
        </p>
      )}

      {draft?.criteria?.map((criterion) => {
        const key = criterion.key;
        const def = criterion.definition;
        const edit = localEdits[key] || { score: '', comment: '' };
        const showAi = expandedAi === key;
        const isEditing = editingKeys.has(key);
        const hasContent =
          criterion.effective?.score != null || criterion.effective?.comment;
        const displayScore = criterion.effective?.score;
        const displayComment = criterion.effective?.comment;

        return (
          <div
            key={key}
            ref={(el) => {
              criterionRefs.current[key] = el;
            }}
            id={`criterion-${key}`}
            className={`rounded-lg border p-5 transition-colors ${
              flashKeys.includes(key)
                ? 'border-primary ring-2 ring-primary/40'
                : criterion.is_overridden
                  ? 'border-amber-500/30 bg-amber-500/[0.03]'
                  : 'border-border'
            }`}
          >
            <div className="flex items-start justify-between mb-4 gap-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h4 className="text-sm font-semibold text-foreground">
                    {def.name}
                  </h4>
                  <OverrideBadge
                    isOverridden={criterion.is_overridden}
                    refinedViaChat={criterion.ai?.refined_via_chat}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {def.description}
                </p>
                {criterion.teacher?.overridden_at && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Overridden{' '}
                    {new Date(criterion.teacher.overridden_at).toLocaleString(
                      'en-GB'
                    )}
                  </p>
                )}
              </div>
              <span className="shrink-0 rounded-full px-2.5 py-0.5 text-xs bg-secondary text-muted-foreground ring-1 ring-border">
                {def.category}
              </span>
            </div>

            {criterion.ai?.evidence_refs?.length > 0 && (
              <div className="mb-4 rounded-md bg-secondary/50 border border-border p-3 space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Grounded evidence (read-only)
                </p>
                {criterion.ai.evidence_refs.slice(0, 2).map((ref, i) => (
                  <div key={i} className="text-[11px]">
                    <span className="font-mono text-primary">
                      {ref.file_name}
                    </span>
                    {ref.quote && (
                      <p className="text-muted-foreground mt-1 line-clamp-2 font-mono">
                        {ref.quote}
                      </p>
                    )}
                    {ref.missing_note && (
                      <p className="text-amber-400 mt-1">{ref.missing_note}</p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {isEditing && !locked ? (
              <div className="rounded-md border border-amber-500/30 bg-amber-500/[0.03] p-4 space-y-4">
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Score (max {def.max_score})
                    </label>
                    <input
                      type="number"
                      min="0"
                      max={def.max_score}
                      step="0.5"
                      value={edit.score}
                      onChange={(e) =>
                        setLocalEdits((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], score: e.target.value },
                        }))
                      }
                      className={inputClass}
                      autoFocus
                    />
                  </div>
                  <div className="col-span-3">
                    <label className="block text-xs font-medium text-muted-foreground mb-1.5">
                      Your explanation
                    </label>
                    <textarea
                      rows={3}
                      value={edit.comment}
                      onChange={(e) =>
                        setLocalEdits((prev) => ({
                          ...prev,
                          [key]: { ...prev[key], comment: e.target.value },
                        }))
                      }
                      placeholder="Provide your reasoning…"
                      className={`${inputClass} resize-none font-sans`}
                    />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      saveOverrides([key], { exitEditMode: true })
                    }
                    disabled={saving}
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {saving ? (
                      <Loader2 size={12} className="animate-spin" />
                    ) : (
                      <CheckCircle2 size={12} />
                    )}
                    Save override
                  </button>
                  <button
                    type="button"
                    onClick={() => cancelEditing(key)}
                    disabled={saving}
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    <X size={12} />
                    Cancel
                  </button>
                </div>
              </div>
            ) : hasContent || locked ? (
              <div className="flex gap-5 items-start">
                <div className="shrink-0 text-center">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                    Score
                  </p>
                  <p className="text-2xl font-mono font-bold text-foreground leading-none">
                    {displayScore ?? '—'}
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    / {def.max_score}
                  </p>
                </div>
                <div className="flex-1 min-w-0 border-l border-border pl-5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">
                    Explanation
                  </p>
                  {displayComment ? (
                    <div className="text-sm text-foreground leading-relaxed">
                      <HighlightedComment text={displayComment} />
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">—</p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic py-2">
                No suggestion yet — generate AI suggestions to populate this
                criterion.
              </p>
            )}

            {!locked && !isEditing && (
              <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-border/50">
                {onDiscussCriterion && (hasContent || criterion.ai) && (
                  <button
                    type="button"
                    onClick={() =>
                      onDiscussCriterion({
                        key,
                        name: def.name,
                        score: displayScore,
                      })
                    }
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    <MessageSquare size={12} />
                    Discuss with AI
                  </button>
                )}
                {(hasContent || criterion.ai) && (
                  <button
                    type="button"
                    onClick={() => startEditing(key)}
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  >
                    <PenLine size={12} />
                    Override
                  </button>
                )}
                {criterion.is_overridden && (
                  <button
                    type="button"
                    onClick={() => handleRevert(key)}
                    disabled={saving}
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md text-amber-400 hover:bg-amber-500/10 transition-colors"
                  >
                    <RotateCcw size={12} />
                    Revert to AI
                  </button>
                )}
                {criterion.ai && (
                  <button
                    type="button"
                    onClick={() => setExpandedAi(showAi ? null : key)}
                    className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-md text-muted-foreground hover:text-foreground transition-colors ml-auto"
                  >
                    <History size={12} />
                    Original AI
                    {showAi ? (
                      <ChevronDown size={12} />
                    ) : (
                      <ChevronRight size={12} />
                    )}
                  </button>
                )}
              </div>
            )}

            {(showAi || locked) && criterion.ai && !isEditing && (
              <div className="mt-3 rounded-md border border-blue-500/20 bg-blue-500/5 p-3 space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-blue-400">
                  Original AI suggestion (preserved)
                </p>
                <p className="text-xs font-mono text-foreground">
                  Score: {criterion.ai.score ?? '—'}
                  {criterion.ai.confidence != null && (
                    <span className="text-muted-foreground ml-2">
                      ({Math.round(criterion.ai.confidence * 100)}% confidence)
                    </span>
                  )}
                </p>
                <HighlightedComment text={criterion.ai.comment} />
                {criterion.teacher && (
                  <div className="pt-2 border-t border-border/50">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-400 mb-1">
                      Teacher override
                    </p>
                    <p className="text-xs font-mono">
                      Score: {criterion.teacher.score ?? '—'}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {criterion.teacher.comment}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {hasSuggestions && (
        <div className="rounded-lg border border-border p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Overall summary (effective)
            </label>
            {locked ? (
              <p className="text-sm text-foreground leading-relaxed">
                {draft.summary?.effective || finalized?.summary || '—'}
              </p>
            ) : (
              <textarea
                rows={3}
                value={localSummary}
                onChange={(e) => setLocalSummary(e.target.value)}
                className={`${inputClass} font-sans resize-none`}
                placeholder={draft.summary?.ai || 'Assessment summary…'}
              />
            )}
            {!locked && draft.summary?.ai && (
              <p className="text-[10px] text-muted-foreground mt-1">
                AI original preserved in transparency log
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <span className="text-muted-foreground">Grade:</span>
            {locked ? (
              <span className="font-mono font-bold text-lg">
                {draft.overall_grade?.effective ||
                  finalized?.overall_grade ||
                  '—'}
              </span>
            ) : (
              <select
                value={localGrade}
                onChange={(e) => setLocalGrade(e.target.value)}
                className="bg-secondary border border-border rounded-md px-3 py-1.5 text-sm font-mono font-bold"
              >
                <option value="">—</option>
                {GRADE_OPTIONS.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            )}
            {draft.overall_score != null && (
              <span className="text-muted-foreground text-xs">
                (avg {draft.overall_score}/10)
              </span>
            )}
          </div>
        </div>
      )}

      {!locked && hasSuggestions && (
        <div className="space-y-3 pt-2 border-t border-border">
          {draft.finalize_blocked_reason && (
            <p className="text-xs text-amber-400 flex items-center gap-1.5">
              <AlertTriangle size={12} />
              {draft.finalize_blocked_reason}
            </p>
          )}
          <label className="block text-xs font-medium text-muted-foreground">
            Finalization notes (optional)
          </label>
          <textarea
            rows={2}
            value={teacherNotes}
            onChange={(e) => setTeacherNotes(e.target.value)}
            placeholder="Any closing remarks before locking the form…"
            className={`${inputClass} font-sans resize-none`}
          />
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={() =>
                saveOverrides(draft.criteria.map((c) => c.key), {
                  includeSummaryGrade: true,
                })
              }
              disabled={saving}
              className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
            >
              {saving ? 'Saving…' : 'Save all overrides'}
            </button>
            <button
              type="button"
              onClick={handleFinalize}
              disabled={finalizing || !draft.can_finalize}
              title={draft.finalize_blocked_reason || undefined}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {finalizing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <CheckCircle2 size={14} />
              )}
              Finalize assessment
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
