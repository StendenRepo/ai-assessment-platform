'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Trash2, Upload, FileText, ArrowRight, Save } from 'lucide-react';
import { apiFetch } from '@/lib/apiFetch';

const CATEGORIES = [
  {
    value: 'technical',
    label: 'Technical',
    badge: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
    dot: 'bg-blue-400',
  },
  {
    value: 'communication',
    label: 'Communication',
    badge: 'bg-purple-500/10 text-purple-400 ring-1 ring-purple-500/20',
    dot: 'bg-purple-400',
  },
  {
    value: 'process',
    label: 'Process',
    badge: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
    dot: 'bg-amber-400',
  },
];

const CATEGORY_BY_VALUE = Object.fromEntries(
  CATEGORIES.map((c) => [c.value, c])
);

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all';

function emptyDraft() {
  return {
    category: 'technical',
    title: '',
    points: '',
    description: '',
  };
}

// Local-only IDs are minted client-side for criteria the user has added but
// not yet persisted. We prefix them so they can never collide with a server
// UUID and so the save logic can tell server vs local rows apart.
function newLocalId() {
  return `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
const isLocalId = (id) => typeof id === 'string' && id.startsWith('local-');

export default function RubricPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.projectId;

  const [criteria, setCriteria] = useState([]);
  // Server-side IDs the user has removed locally. These are DELETEd on
  // "Save Draft" and ignored by "Complete Setup" (which replaces wholesale).
  const [deletedIds, setDeletedIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [draft, setDraft] = useState(emptyDraft());
  const [draftErrors, setDraftErrors] = useState({});
  const [showDraft, setShowDraft] = useState(false);

  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saveNotice, setSaveNotice] = useState(null);

  useEffect(() => {
    if (!projectId) return;
    apiFetch(`/projects/${projectId}/rubric`)
      .then(setCriteria)
      .catch((err) => setLoadError(err.message || 'Failed to load criteria'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const grouped = useMemo(() => {
    const buckets = Object.fromEntries(CATEGORIES.map((c) => [c.value, []]));
    for (const c of criteria) {
      if (buckets[c.category]) buckets[c.category].push(c);
      else buckets[c.category] = [c];
    }
    return buckets;
  }, [criteria]);

  const totalPoints = useMemo(
    () => criteria.reduce((sum, c) => sum + (Number(c.points) || 0), 0),
    [criteria]
  );

  function validateDraft() {
    const errors = {};
    if (!draft.title.trim()) errors.title = 'Title is required';
    const pts = Number(draft.points);
    if (!draft.points || Number.isNaN(pts) || pts <= 0)
      errors.points = 'Points must be a positive number';
    if (!CATEGORY_BY_VALUE[draft.category])
      errors.category = 'Invalid category';
    return errors;
  }

  function handleAddDraft() {
    const errors = validateDraft();
    if (Object.keys(errors).length) {
      setDraftErrors(errors);
      return;
    }
    setCriteria((prev) => [
      ...prev,
      {
        id: newLocalId(),
        project_id: projectId,
        category: draft.category,
        title: draft.title.trim(),
        description: draft.description.trim() || null,
        points: Number(draft.points),
        position: prev.filter((c) => c.category === draft.category).length,
      },
    ]);
    setDraft(emptyDraft());
    setDraftErrors({});
    setShowDraft(false);
  }

  function handleRemove(id) {
    setCriteria((prev) => prev.filter((c) => c.id !== id));
    if (!isLocalId(id)) {
      setDeletedIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
    }
  }

  // "Save Draft": persist local changes via per-row endpoints; do NOT flip
  // project.status. POST any locally-added criteria, DELETE anything the user
  // removed from a previously-saved state. Editing existing rows is not
  // wired into the UI yet, so PATCH is unused here.
  async function handleSaveDraft() {
    setSaveError(null);
    setSaveNotice(null);
    setSaving(true);
    try {
      // DELETEs first so a re-added title with the same name doesn't trip a
      // future unique constraint, and so we surface delete errors clearly.
      for (const id of deletedIds) {
        await apiFetch(`/projects/${projectId}/rubric/${id}`, {
          method: 'DELETE',
        });
      }

      // POST each local-id criterion and swap the local row for the server
      // copy so subsequent saves see it as already-persisted.
      const updated = [...criteria];
      for (let i = 0; i < updated.length; i++) {
        const c = updated[i];
        if (!isLocalId(c.id)) continue;
        const saved = await apiFetch(`/projects/${projectId}/rubric`, {
          method: 'POST',
          json: {
            category: c.category,
            title: c.title,
            description: c.description || null,
            points: Number(c.points),
            position: c.position ?? i,
          },
        });
        updated[i] = saved;
      }

      setCriteria(updated);
      setDeletedIds([]);
      setSaveNotice('Draft saved.');
    } catch (err) {
      setSaveError(err.message || 'Failed to save draft');
    } finally {
      setSaving(false);
    }
  }

  // "Complete Setup": atomic bulk save on the backend that also flips
  // project.status to "ready".
  async function handleCompleteSetup() {
    setSaveError(null);
    setSaveNotice(null);
    if (criteria.length === 0) {
      setSaveError('Add at least one criterion before completing setup.');
      return;
    }
    setCompleting(true);
    try {
      await apiFetch(`/projects/${projectId}/rubric/save`, {
        method: 'POST',
        json: {
          criteria: criteria.map((c, idx) => ({
            category: c.category,
            title: c.title,
            description: c.description || null,
            points: Number(c.points),
            position: idx,
          })),
        },
      });
      router.push(`/projects/${projectId}`);
    } catch (err) {
      setSaveError(err.message || 'Failed to complete setup');
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb is rendered globally by the app layout's <Breadcrumb /> */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Assessment Criteria &amp; Rubrics
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Define criteria for evaluating this project&apos;s students
        </p>
      </div>

      {/* Import card (stubbed) */}
      <div className="rounded-lg bg-card border border-border p-6 space-y-3">
        <h2 className="text-sm font-semibold text-foreground">
          Import Existing Rubric (Optional)
        </h2>
        <div className="flex gap-3">
          <button
            type="button"
            disabled
            title="Coming in a later sprint"
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground opacity-60 cursor-not-allowed"
          >
            <Upload size={14} /> Import from file
          </button>
          <button
            type="button"
            disabled
            title="Coming in a later sprint"
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground opacity-60 cursor-not-allowed"
          >
            <FileText size={14} /> Load template
          </button>
        </div>
      </div>

      <div className="rounded-lg bg-card border border-border p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h2 className="text-sm font-semibold text-foreground">
              Criteria ({criteria.length})
            </h2>
            <p className="text-xs text-muted-foreground">
              {totalPoints} total points
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setShowDraft(true);
              setDraftErrors({});
            }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus size={14} /> Add Criterion
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {loadError && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {loadError}
          </div>
        )}

        {!loading && !loadError && criteria.length === 0 && !showDraft && (
          <div className="rounded-lg border border-dashed border-border px-6 py-10 text-center">
            <p className="text-sm text-muted-foreground">
              No criteria yet. Add the first one to get started.
            </p>
          </div>
        )}

        {!loading &&
          CATEGORIES.map((cat) => {
            const rows = grouped[cat.value] || [];
            if (rows.length === 0) return null;
            return (
              <div key={cat.value} className="space-y-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${cat.badge}`}
                  >
                    {cat.label}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {rows.length} {rows.length === 1 ? 'criterion' : 'criteria'}
                  </span>
                </div>
                <div className="space-y-2">
                  {rows.map((c) => (
                    <div
                      key={c.id}
                      className="flex items-start gap-4 rounded-md border border-border bg-background px-4 py-3"
                    >
                      <div
                        className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${cat.dot}`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold text-foreground">
                            {c.title}
                          </span>
                          <span className="text-xs font-mono text-muted-foreground bg-secondary px-2 py-0.5 rounded">
                            {c.points} pts
                          </span>
                        </div>
                        {c.description && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {c.description}
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemove(c.id)}
                        className="text-muted-foreground hover:text-red-400 transition-colors p-1"
                        aria-label="Delete criterion"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

        {showDraft && (
          <div className="rounded-md border border-border bg-background p-4 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Category
                </label>
                <select
                  value={draft.category}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, category: e.target.value }))
                  }
                  className={inputClass}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1 col-span-1">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Points
                </label>
                <input
                  type="number"
                  min="1"
                  value={draft.points}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, points: e.target.value }))
                  }
                  placeholder="10"
                  className={inputClass}
                />
                {draftErrors.points && (
                  <p className="text-xs text-red-400">{draftErrors.points}</p>
                )}
              </div>
              <div className="space-y-1 col-span-1">
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Title
                </label>
                <input
                  type="text"
                  value={draft.title}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, title: e.target.value }))
                  }
                  placeholder="Code Quality"
                  className={inputClass}
                />
                {draftErrors.title && (
                  <p className="text-xs text-red-400">{draftErrors.title}</p>
                )}
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Description (optional)
              </label>
              <textarea
                value={draft.description}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, description: e.target.value }))
                }
                rows={2}
                placeholder="What you're looking for in this criterion..."
                className={`${inputClass} resize-none`}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowDraft(false);
                  setDraft(emptyDraft());
                  setDraftErrors({});
                }}
                className="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAddDraft}
                className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
              >
                Add
              </button>
            </div>
          </div>
        )}
      </div>

      {saveError && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {saveError}
        </div>
      )}
      {saveNotice && !saveError && (
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">
          {saveNotice}
        </div>
      )}

      <div className="flex justify-between">
        <button
          type="button"
          onClick={() => router.push('/projects')}
          className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
        >
          Back to projects
        </button>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleSaveDraft}
            disabled={saving || completing}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md border border-border text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-50 transition-colors"
          >
            <Save size={14} /> {saving ? 'Saving…' : 'Save Draft'}
          </button>
          <button
            type="button"
            onClick={handleCompleteSetup}
            disabled={saving || completing || criteria.length === 0}
            className="flex items-center gap-1.5 px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {completing ? 'Completing…' : 'Complete Setup'}
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
