'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { FileText, Scale, Upload, Trash2, Check, Pencil } from 'lucide-react';
import {
  listModuleRubrics,
  addModuleRubric,
  updateModuleRubric,
  deleteModuleRubric,
} from '@/lib/api/modulesApi';

function WeightField({ rubric, onConfirm }) {
  const [editing, setEditing] = useState(rubric.weight == null);
  const [value, setValue] = useState(
    rubric.weight != null ? String(rubric.weight) : ''
  );
  const [saving, setSaving] = useState(false);

  const confirm = async () => {
    setSaving(true);
    try {
      await onConfirm(value);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-xs text-muted-foreground">
          weight{' '}
          <span className="font-semibold text-foreground">{rubric.weight}</span>
        </span>
        <button
          type="button"
          onClick={() => setEditing(true)}
          title="Change weight"
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
        >
          <Pencil size={13} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <input
        type="number"
        min="0"
        max="1"
        step="0.05"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && confirm()}
        placeholder="weight"
        autoFocus
        className="w-16 bg-background border border-border rounded-md px-2 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <button
        type="button"
        onClick={confirm}
        disabled={saving}
        title="Save weight"
        className="p-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60"
      >
        {saving ? (
          <span className="w-3.5 h-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin block" />
        ) : (
          <Check size={14} />
        )}
      </button>
    </div>
  );
}

export default function ModuleRubricsPanel({ moduleId }) {
  const [rubrics, setRubrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const fileRef = useRef(null);

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

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError('');
    setAdding(true);
    try {
      await addModuleRubric(moduleId, file, null, null);
      if (fileRef.current) fileRef.current.value = '';
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  };

  const handleWeight = async (rubric, value) => {
    const updated = await updateModuleRubric(moduleId, rubric.id, {
      weight: value === '' ? null : Number(value),
    });
    setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? updated : r)));
  };

  const handleDelete = async (rubric) => {
    setError('');
    try {
      await deleteModuleRubric(moduleId, rubric.id);
      setRubrics((prev) => prev.filter((r) => r.id !== rubric.id));
    } catch (err) {
      setError(err.message);
    }
  };

  const totalWeight = rubrics.reduce((s, r) => s + (Number(r.weight) || 0), 0);
  const weightsSet = rubrics.some((r) => r.weight != null);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
          <Scale size={16} />
          Rubrics
        </h3>
        {weightsSet && (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ${
              Math.abs(totalWeight - 1) < 0.001
                ? 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20'
                : 'bg-amber-500/10 text-amber-400 ring-amber-500/20'
            }`}
            title="Weights should add up to 1.0"
          >
            Σ {totalWeight.toFixed(2)}
          </span>
        )}
      </div>

      <div className="rounded-lg bg-card border border-border px-5 pt-5 pb-5 space-y-4">
        <p className="text-xs text-muted-foreground">
          Attach multiple rubrics (e.g. report, reflection), each with a weight.
          Weights should add up to 1.0.
        </p>

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
            <div className="space-y-2">
              {rubrics.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center gap-3 rounded-lg bg-secondary border border-border px-3 py-3"
                >
                  <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText size={16} className="text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-semibold text-foreground truncate block">
                      {r.name || r.file_name || 'Rubric'}
                    </span>
                    <div className="text-xs text-muted-foreground mt-0.5 font-mono truncate">
                      {r.file_name}
                    </div>
                  </div>
                  <WeightField
                    rubric={r}
                    onConfirm={(value) => handleWeight(r, value)}
                  />
                  <button
                    type="button"
                    onClick={() => handleDelete(r)}
                    title="Remove rubric"
                    className="shrink-0 flex items-center justify-center p-2 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10 transition-all"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )
        )}

        <div className="pt-1 space-y-2">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.xlsx"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={adding}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md border border-border bg-secondary text-sm font-semibold text-foreground hover:bg-secondary/70 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <Upload size={15} />
            {adding ? 'Uploading…' : 'Choose file'}
          </button>
          <p className="text-[10px] text-muted-foreground">
            Upload a rubric, then set its weight as the next step.
          </p>
        </div>
      </div>
    </div>
  );
}
