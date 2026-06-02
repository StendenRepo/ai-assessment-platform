'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Trash2, Upload } from 'lucide-react';
import { mockCriteria } from '@/lib/mockData';
import { APP_PATHS } from '@/lib/routes';

const CATEGORIES = ['Technical', 'Communication', 'Process', 'Collaboration'];

const categoryColors = {
  Technical: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
  Communication: 'bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20',
  Process: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
  Collaboration:
    'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
};

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

export default function CriteriaPage() {
  const router = useRouter();
  const [criteria, setCriteria] = useState(mockCriteria);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '',
    description: '',
    maxScore: 10,
    category: 'Technical',
  });

  const handleAdd = () => {
    setCriteria([...criteria, { id: `crit-${Date.now()}`, ...form }]);
    setShowForm(false);
    setForm({ name: '', description: '', maxScore: 10, category: 'Technical' });
  };

  const totalPoints = criteria.reduce((s, c) => s + c.maxScore, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Assessment Criteria & Rubrics
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Define criteria for evaluating this project's students
        </p>
      </div>

      <div className="max-w-3xl space-y-5">
        <div className="rounded-lg bg-secondary border border-border p-5">
          <p className="text-xs font-medium text-muted-foreground mb-3">
            Import Existing Rubric (Optional)
          </p>
          <div className="flex gap-2">
            <button className="flex items-center gap-2 px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card transition-all">
              <Upload size={13} /> Import from file
            </button>
            <button className="flex items-center gap-2 px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card transition-all">
              Load template
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              Criteria ({criteria.length})
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              {totalPoints} total points
            </p>
          </div>
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
          >
            <Plus size={13} /> Add Criterion
          </button>
        </div>

        {showForm && (
          <div className="rounded-lg bg-card border border-border p-5 space-y-4">
            <h3 className="text-sm font-semibold text-foreground">
              New Criterion
            </h3>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Name *
              </label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Code Quality"
                className={inputClass}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Description *
              </label>
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={2}
                placeholder="Describe what will be assessed..."
                className={`${inputClass} resize-none`}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Category *
                </label>
                <select
                  value={form.category}
                  onChange={(e) =>
                    setForm({ ...form, category: e.target.value })
                  }
                  className={inputClass}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Maximum Score *
                </label>
                <input
                  type="number"
                  value={form.maxScore}
                  onChange={(e) =>
                    setForm({ ...form, maxScore: parseInt(e.target.value) })
                  }
                  min="1"
                  max="100"
                  className={inputClass}
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowForm(false)}
                className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                disabled={!form.name || !form.description}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Save Criterion
              </button>
            </div>
          </div>
        )}

        {CATEGORIES.map((category) => {
          const cats = criteria.filter((c) => c.category === category);
          if (cats.length === 0) return null;
          return (
            <div key={category}>
              <div className="flex items-center gap-2 mb-2">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${categoryColors[category]}`}
                >
                  {category}
                </span>
                <span className="text-xs text-muted-foreground">
                  {cats.length} criteria
                </span>
              </div>
              <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
                {cats.map((criterion) => (
                  <div
                    key={criterion.id}
                    className="flex items-start gap-4 px-5 py-4"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-semibold text-foreground">
                          {criterion.name}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono">
                          {criterion.maxScore} pts
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {criterion.description}
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        setCriteria(
                          criteria.filter((c) => c.id !== criterion.id)
                        )
                      }
                      className="text-muted-foreground hover:text-destructive transition-colors mt-0.5 shrink-0"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        <div className="flex gap-3 justify-end pt-2 border-t border-border">
          <button className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
            Save Draft
          </button>
          <button
            onClick={() => router.push(APP_PATHS.dashboard)}
            className="px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
          >
            Complete Setup →
          </button>
        </div>
      </div>
    </div>
  );
}
