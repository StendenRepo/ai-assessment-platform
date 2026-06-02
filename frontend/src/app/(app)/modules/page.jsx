'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { BookOpen, Plus, ArrowRight, FileText } from 'lucide-react';
import { listModules, createModule } from '@/lib/modulesApi';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

export default function ModulesPage() {
  const router = useRouter();
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', academic_year: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listModules()
      .then(setModules)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const created = await createModule({
        name: form.name.trim(),
        academic_year: form.academic_year.trim() || null,
      });
      setModules((prev) => [created, ...prev]);
      setShowForm(false);
      setForm({ name: '', academic_year: '' });
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Modules</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your modules and their rubrics
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
        >
          <Plus size={13} /> New Module
        </button>
      </div>

      {showForm && (
        <div className="max-w-lg rounded-lg bg-card border border-border p-5 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">New Module</h3>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Module Name *
            </label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Advanced Web Development"
              className={inputClass}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Academic Year
            </label>
            <input
              value={form.academic_year}
              onChange={(e) => setForm({ ...form, academic_year: e.target.value })}
              placeholder="e.g. 2025-2026"
              className={inputClass}
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setShowForm(false); setForm({ name: '', academic_year: '' }); }}
              className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!form.name.trim() || saving}
              className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? 'Creating...' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : modules.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <BookOpen size={32} className="text-muted-foreground mb-3" />
          <p className="text-sm font-medium text-foreground">No modules yet</p>
          <p className="text-xs text-muted-foreground mt-1">
            Create your first module to get started
          </p>
        </div>
      ) : (
        <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
          {modules.map((mod) => (
            <div
              key={mod.id}
              onClick={() => router.push(`/modules/${mod.id}`)}
              className="flex items-center gap-5 px-6 py-4 hover:bg-secondary/50 cursor-pointer transition-colors"
            >
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <BookOpen size={16} className="text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-foreground truncate">
                  {mod.name}
                </div>
                <div className="flex items-center gap-3 mt-0.5 text-xs text-muted-foreground">
                  {mod.academic_year && <span>{mod.academic_year}</span>}
                  {mod.rubric_file ? (
                    <span className="flex items-center gap-1 text-emerald-400">
                      <FileText size={11} /> Rubric attached
                    </span>
                  ) : (
                    <span className="text-amber-400">No rubric</span>
                  )}
                </div>
              </div>
              <ArrowRight size={14} className="text-muted-foreground shrink-0" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
