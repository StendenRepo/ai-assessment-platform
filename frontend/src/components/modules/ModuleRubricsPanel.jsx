'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { FileText, Plus, Trash2, AlertTriangle, Scale } from 'lucide-react';
import {
  listModuleRubrics,
  addModuleRubric,
  updateModuleRubric,
  deleteModuleRubric,
} from '@/lib/api/modulesApi';

export default function ModuleRubricsPanel({ moduleId }) {
  const [rubrics, setRubrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [weight, setWeight] = useState('');
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

  const handleAdd = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError('Choose a rubric file first (.pdf or .xlsx).');
      return;
    }
    setError('');
    setAdding(true);
    try {
      await addModuleRubric(
        moduleId,
        file,
        name.trim() || null,
        weight === '' ? null : Number(weight)
      );
      setName('');
      setWeight('');
      if (fileRef.current) fileRef.current.value = '';
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setAdding(false);
    }
  };

  const handleWeight = async (rubric, value) => {
    try {
      const updated = await updateModuleRubric(moduleId, rubric.id, {
        weight: value === '' ? null : Number(value),
      });
      setRubrics((prev) => prev.map((r) => (r.id === rubric.id ? updated : r)));
    } catch (err) {
      setError(err.message);
    }
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

  const inputClass =
    'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Scale size={14} className="text-accent" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-foreground">Rubrics</div>
          <div className="text-[11px] text-muted-foreground">
            Attach multiple rubrics (e.g. report, reflection) each with a weight
          </div>
        </div>
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

      <div className="p-4 space-y-3">
        {error && (
          <div className="flex items-start gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2">
            <AlertTriangle size={12} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-[11px] text-red-400 leading-relaxed">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-6">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : rubrics.length === 0 ? (
          <p className="text-[11px] text-muted-foreground px-1">
            No rubrics yet. Add one below.
          </p>
        ) : (
          rubrics.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 rounded-md bg-secondary/40 border border-border px-3 py-2.5"
            >
              <FileText size={13} className="text-muted-foreground shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-foreground truncate">
                  {r.name || r.file_name || 'Rubric'}
                </div>
                <div className="text-[10px] text-muted-foreground font-mono truncate">
                  {r.file_name}
                </div>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className="text-[10px] text-muted-foreground">weight</span>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  defaultValue={r.weight ?? ''}
                  onBlur={(e) => handleWeight(r, e.target.value)}
                  placeholder="—"
                  className="w-16 bg-background border border-border rounded px-2 py-1 text-[11px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <button
                onClick={() => handleDelete(r)}
                title="Remove rubric"
                className="shrink-0 p-1.5 rounded-md border border-border text-muted-foreground hover:text-red-400 hover:border-red-500/30 transition-colors cursor-pointer"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}

        <form
          onSubmit={handleAdd}
          className="rounded-md border border-dashed border-border p-3 space-y-2"
        >
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.xlsx"
            className="block w-full text-[11px] text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-foreground hover:file:bg-secondary/70 file:cursor-pointer"
          />
          <div className="flex gap-2">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name (e.g. Report)"
              className={`${inputClass} flex-1`}
            />
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="Weight"
              className={`${inputClass} w-24`}
            />
            <button
              type="submit"
              disabled={adding}
              className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {adding ? (
                <span className="w-3.5 h-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                <Plus size={13} />
              )}
              Add
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
