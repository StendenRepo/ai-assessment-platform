'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, Trash2, Upload, Loader2, CheckCircle2 } from 'lucide-react';
import { platformApi } from '@/lib/platformApi';
import { inputCls } from '@/lib/formStyles';

const CATEGORIES = ['Technical', 'Communication', 'Process', 'Collaboration'];

const categoryColors = {
  Technical: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
  Communication: 'bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20',
  Process: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
  Collaboration: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
};

export default function CriteriaPage() {
  const { projectId } = useParams();
  const router = useRouter();
  const [criteria, setCriteria] = useState([]);
  const [hasRubric, setHasRubric] = useState(false);
  const [hasGuide, setHasGuide] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      await platformApi.ensureGroup(projectId, 'group-1').catch(() => {});
      const mod = await platformApi.getModule(projectId);
      setHasRubric(mod.has_rubric);
      setHasGuide(mod.has_module_guide);
      setCriteria(
        (mod.criteria || []).map((c, i) => ({
          id: c.id || `c-${i}`,
          name: c.title || c.name || 'Criterion',
          description: c.description || '',
          maxScore: 10,
          category: CATEGORIES[i % CATEGORIES.length],
        }))
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [projectId]);

  const uploadRubric = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading('rubric');
    setMessage(null);
    try {
      const res = await platformApi.uploadRubric(projectId, file);
      setMessage(`Rubric imported (${res.criteria?.length ?? 0} criteria)`);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(null);
      e.target.value = '';
    }
  };

  const uploadGuide = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading('guide');
    try {
      await platformApi.uploadModuleGuide(projectId, file);
      setMessage('Module guide uploaded');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(null);
      e.target.value = '';
    }
  };

  const totalPoints = criteria.reduce((s, c) => s + c.maxScore, 0);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Assessment Criteria & Rubrics
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Import rubrics and module guides for AI analysis (project {projectId})
        </p>
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-2">
          {error}
        </p>
      )}
      {message && (
        <p className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md px-4 py-2 flex items-center gap-2">
          <CheckCircle2 size={16} /> {message}
        </p>
      )}

      <div className="max-w-3xl space-y-5">
        <div className="rounded-lg bg-card border border-border p-5 space-y-4">
          <p className="text-xs font-medium text-muted-foreground">
            Import from file (POC)
          </p>
          <div className="flex flex-wrap gap-2">
            <label className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary cursor-pointer transition-colors">
              {uploading === 'rubric' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Upload size={14} />
              )}
              {hasRubric ? 'Replace rubric' : 'Upload rubric'}
              <input type="file" className="hidden" onChange={uploadRubric} accept=".txt,.md,.pdf,.docx" />
            </label>
            <label className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary cursor-pointer transition-colors">
              {uploading === 'guide' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Upload size={14} />
              )}
              {hasGuide ? 'Replace guide' : 'Upload module guide'}
              <input type="file" className="hidden" onChange={uploadGuide} />
            </label>
            {hasRubric && (
              <button
                type="button"
                onClick={async () => {
                  await platformApi.removeRubric(projectId);
                  await load();
                }}
                className="px-3 py-2 text-xs text-muted-foreground hover:text-red-400"
              >
                Remove rubric
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              Criteria ({criteria.length})
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              From imported rubric or defaults · {totalPoints} pts (display)
            </p>
          </div>
        </div>

        {criteria.length === 0 ? (
          <p className="text-sm text-muted-foreground">No criteria loaded.</p>
        ) : (
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {criteria.map((criterion) => (
              <div key={criterion.id} className="px-5 py-4">
                <div className="flex items-start gap-3">
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase ${categoryColors[criterion.category] || categoryColors.Technical}`}
                  >
                    {criterion.category}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground">
                      {criterion.name}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {criterion.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-3 justify-end pt-2 border-t border-border">
          <button
            type="button"
            onClick={() => router.push(`/projects/${projectId}`)}
            className="px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
          >
            Continue to groups →
          </button>
        </div>
      </div>
    </div>
  );
}
