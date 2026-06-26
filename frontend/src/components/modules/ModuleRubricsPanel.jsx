'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  AlertTriangle,
  Check,
  Download,
  Eye,
  FileText,
  RefreshCw,
  Scale,
  Trash2,
  Upload,
} from 'lucide-react';
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog';
import EvidenceStatusIndicator from '@/components/evidence/EvidenceStatusIndicator';
import {
  listModuleRubrics,
  addModuleRubric,
  updateModuleRubric,
  deleteModuleRubric,
  getModuleRubricFileBlob,
} from '@/lib/api/modulesApi';
import { getPreviewKind } from '@/lib/hooks/useDocumentPreview';

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

function WeightBadge({ rubric, onConfirm }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(
    rubric.weight != null ? String(rubric.weight) : ''
  );
  const [saving, setSaving] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    setValue(rubric.weight != null ? String(rubric.weight) : '');
  }, [rubric.weight]);

  const confirm = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await onConfirm(value);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative shrink-0" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Edit weight"
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-primary/10 border border-primary/20 hover:bg-primary/20 hover:border-primary/40 transition-colors cursor-pointer"
      >
        <Scale size={11} className="text-primary" />
        <span className="text-xs font-semibold text-primary">
          {rubric.weight != null ? rubric.weight : '—'}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 z-20 w-44 rounded-lg bg-card border border-border shadow-lg p-3 space-y-2">
          <p className="text-xs text-muted-foreground">Weight (0 – 1)</p>
          <div className="flex items-center gap-1.5">
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') confirm();
                if (e.key === 'Escape') setOpen(false);
              }}
              autoFocus
              placeholder="0.00"
              className="flex-1 min-w-0 bg-background border border-border rounded-md px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="button"
              onClick={confirm}
              disabled={saving}
              className="shrink-0 p-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60 cursor-pointer"
            >
              {saving ? (
                <span className="w-3 h-3 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin block" />
              ) : (
                <Check size={12} />
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ModuleRubricsPanel({
  moduleId,
  viewOnly = false,
  docPreview,
}) {
  const [rubrics, setRubrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [pendingReplace, setPendingReplace] = useState(null);

  const addFileRef = useRef(null);
  const replaceFileRef = useRef(null);
  const replaceTargetRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRubrics(await listModuleRubrics(moduleId));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [moduleId]);

  useEffect(() => {
    if (moduleId) load();
  }, [moduleId, load]);

  const makeDescriptor = (r) => ({
    file_name: r.name || r.file_name || 'rubric',
    file_type: r.file_type,
    fetchBlob: () => getModuleRubricFileBlob(moduleId, r.id),
    fetchContent: null,
    supportsAltText: false,
  });

  // ── Add ───────────────────────────────────────────────────────────────────

  const handleAddFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setAdding(true);
    try {
      const newRubric = await addModuleRubric(moduleId, file, null, null);
      if (addFileRef.current) addFileRef.current.value = '';
      const updatedList = [...rubrics, newRubric];
      if (updatedList.length === 1) {
        const withWeight = await updateModuleRubric(moduleId, newRubric.id, {
          weight: 1,
        });
        setRubrics([withWeight]);
      } else {
        await load();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  };

  // ── Replace ───────────────────────────────────────────────────────────────

  const requestReplace = (rubric) => {
    replaceTargetRef.current = rubric;
    replaceFileRef.current?.click();
  };

  const handleReplaceFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const target = replaceTargetRef.current;
    if (!target) return;
    setPendingReplace({ rubric: target, file, newName: file.name });
    if (replaceFileRef.current) replaceFileRef.current.value = '';
  };

  const confirmReplace = async () => {
    if (!pendingReplace) return;
    const { rubric, file } = pendingReplace;
    setReplacing(true);
    try {
      const added = await addModuleRubric(moduleId, file, rubric.name, null);
      await updateModuleRubric(moduleId, added.id, { weight: rubric.weight });
      await deleteModuleRubric(moduleId, rubric.id);
      setPendingReplace(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setReplacing(false);
    }
  };

  // ── Weight ────────────────────────────────────────────────────────────────

  const handleWeight = async (rubric, value) => {
    const newWeight = value === '' ? null : Number(value);
    try {
      const updated = await updateModuleRubric(moduleId, rubric.id, {
        weight: newWeight,
      });

      if (newWeight != null && rubrics.length === 2) {
        const other = rubrics.find((r) => r.id !== rubric.id);
        const complement = parseFloat((1 - newWeight).toFixed(2));
        const updatedOther = await updateModuleRubric(moduleId, other.id, {
          weight: complement,
        });
        setRubrics((prev) =>
          prev.map((r) =>
            r.id === rubric.id ? updated : r.id === other.id ? updatedOther : r
          )
        );
      } else {
        setRubrics((prev) =>
          prev.map((r) => (r.id === rubric.id ? updated : r))
        );
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // ── Delete ────────────────────────────────────────────────────────────────

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await deleteModuleRubric(moduleId, pendingDelete.id);
      const remaining = rubrics.filter((r) => r.id !== pendingDelete.id);
      setPendingDelete(null);
      if (remaining.length === 1 && remaining[0].weight !== 1) {
        const withWeight = await updateModuleRubric(moduleId, remaining[0].id, {
          weight: 1,
        });
        setRubrics([withWeight]);
      } else {
        setRubrics(remaining);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(false);
    }
  };

  // ── Derived ───────────────────────────────────────────────────────────────

  const totalWeight = rubrics.reduce((s, r) => s + (Number(r.weight) || 0), 0);
  const multipleRubrics = rubrics.length > 1;
  const weightsSet = multipleRubrics && rubrics.some((r) => r.weight != null);
  const displayName = (r) =>
    (r.name || r.file_name || 'Rubric').replace(/\.[^.]+$/, '');

  return (
    <>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Scale size={16} />
            Rubrics
          </h3>
        </div>

        <div
          className={`rounded-lg bg-card border border-border px-5 pt-5 space-y-4 ${rubrics.length > 0 ? 'pb-3' : 'pb-5'}`}
        >
          <p className="text-xs text-muted-foreground">
            Upload the rubric so the AI knows the grading criteria. Only{' '}
            <span className="font-semibold text-foreground">PDF</span> or{' '}
            <span className="font-semibold text-foreground">Excel</span> (.xlsx)
            files are accepted.
            {multipleRubrics && (
              <>
                {' '}
                Assign a weight to each — they should add up to{' '}
                <span className="font-semibold text-foreground">1.0</span>.
              </>
            )}
          </p>

          {weightsSet && Math.abs(totalWeight - 1) >= 0.001 && (
            <div className="flex items-center gap-2 rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-400">
              <AlertTriangle size={13} className="shrink-0" />
              Weights add up to{' '}
              <span className="font-semibold">{totalWeight.toFixed(2)}</span> —
              they should total <span className="font-semibold">1.0.</span>
            </div>
          )}

          {error && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-6">
              <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            rubrics.length > 0 && (
              <div className="divide-y divide-border -mx-5">
                {rubrics.map((r) => {
                  const descriptor = makeDescriptor(r);
                  const canPreview = getPreviewKind(r.file_type) !== null;
                  return (
                    <div key={r.id} className="space-y-1.5 px-5 py-4">
                      {/* File card */}
                      <div className="flex items-center gap-3 rounded-lg bg-secondary border border-border px-3 py-3">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                          <FileText size={16} className="text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-foreground truncate">
                              {displayName(r)}
                            </span>
                            <EvidenceStatusIndicator
                              status="completed"
                              size={13}
                            />
                          </div>
                          {r.uploaded_at && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              Uploaded {formatDate(r.uploaded_at)}
                            </p>
                          )}
                        </div>
                        {multipleRubrics && (
                          <WeightBadge
                            rubric={r}
                            onConfirm={(value) => handleWeight(r, value)}
                          />
                        )}
                      </div>

                      {/* Action buttons */}
                      <div className="flex gap-2">
                        {canPreview && (
                          <button
                            type="button"
                            onClick={() => docPreview.openPreview(descriptor)}
                            title="Preview"
                            className="flex-1 flex items-center justify-center p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
                          >
                            <Eye size={14} />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => docPreview.download(descriptor)}
                          title="Download"
                          className="flex-1 flex items-center justify-center p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
                        >
                          <Download size={14} />
                        </button>
                        {!viewOnly && (
                          <>
                            <button
                              type="button"
                              onClick={() => requestReplace(r)}
                              disabled={replacing}
                              title="Replace file"
                              className="flex-1 flex items-center justify-center p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-50"
                            >
                              <RefreshCw size={14} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setPendingDelete(r)}
                              disabled={deleting}
                              title="Remove"
                              className="flex-1 flex items-center justify-center p-2 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50"
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          )}

          {!viewOnly && (
            <div className="pt-1 space-y-2">
              <input
                ref={addFileRef}
                type="file"
                accept=".pdf,.xlsx"
                onChange={handleAddFile}
                className="hidden"
              />
              <input
                ref={replaceFileRef}
                type="file"
                accept=".pdf,.xlsx"
                onChange={handleReplaceFile}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => addFileRef.current?.click()}
                disabled={adding}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md border border-border bg-secondary text-sm font-semibold text-foreground hover:bg-secondary/70 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <Upload size={15} />
                {adding ? 'Uploading…' : 'Add rubric'}
              </button>
            </div>
          )}
        </div>
      </div>

      <DeleteConfirmDialog
        open={Boolean(pendingDelete)}
        title="Remove Rubric"
        message={
          <>
            Remove{' '}
            <span className="font-semibold text-foreground">
              {pendingDelete && displayName(pendingDelete)}
            </span>{' '}
            from this module?
          </>
        }
        confirmLabel="Remove"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      <DeleteConfirmDialog
        open={Boolean(pendingReplace)}
        title="Replace Rubric"
        confirmLabel="Replace"
        loading={replacing}
        message={
          <>
            Replace{' '}
            <span className="font-semibold text-foreground">
              {pendingReplace && displayName(pendingReplace.rubric)}
            </span>{' '}
            with{' '}
            <span className="font-semibold text-foreground">
              {pendingReplace?.newName}
            </span>
            ?
          </>
        }
        onConfirm={confirmReplace}
        onCancel={() => setPendingReplace(null)}
      />
    </>
  );
}
