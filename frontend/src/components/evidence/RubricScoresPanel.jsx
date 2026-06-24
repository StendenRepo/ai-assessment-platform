'use client';

import { useState, useEffect, useCallback } from 'react';
import { Scale, Sparkles, AlertTriangle, RefreshCw } from 'lucide-react';
import { listModuleRubrics } from '@/lib/api/modulesApi';
import {
  listRubricScores,
  generateRubricScore,
  getFinalGrade,
  overrideRubricScore,
} from '@/lib/api/rubricScores';

export default function RubricScoresPanel({ studentId, moduleId }) {
  const [rubrics, setRubrics] = useState([]);
  const [scores, setScores] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [scoringId, setScoringId] = useState(null);
  const [finalGrade, setFinalGrade] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, s, fg] = await Promise.all([
        moduleId ? listModuleRubrics(moduleId) : Promise.resolve([]),
        listRubricScores(studentId),
        getFinalGrade(studentId),
      ]);
      setRubrics(r ?? []);
      const map = {};
      (s ?? []).forEach((x) => {
        map[x.rubric_id] = x;
      });
      setScores(map);
      setFinalGrade(fg ?? null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [studentId, moduleId]);

  useEffect(() => {
    if (studentId) load();
  }, [studentId, load]);

  const handleGenerate = async (rubric) => {
    setError('');
    setScoringId(rubric.id);
    try {
      const result = await generateRubricScore(studentId, rubric.id);
      setScores((prev) => ({ ...prev, [rubric.id]: result }));
      setFinalGrade(await getFinalGrade(studentId));
    } catch (err) {
      setError(err.message);
    } finally {
      setScoringId(null);
    }
  };

  const handleOverride = async (rubric, raw) => {
    const trimmed = raw.trim();
    const score = trimmed === '' ? null : Number(trimmed);
    if (score != null && (Number.isNaN(score) || score < 0 || score > 10)) {
      setError('Override must be a number between 0 and 10.');
      return;
    }
    const current = scores[rubric.id];
    if (current && (current.teacher_score ?? null) === score) return;
    setError('');
    try {
      const result = await overrideRubricScore(studentId, rubric.id, score);
      setScores((prev) => ({ ...prev, [rubric.id]: result }));
      setFinalGrade(await getFinalGrade(studentId));
    } catch (err) {
      setError(err.message);
    }
  };

  const hasFinal = finalGrade && finalGrade.score != null;

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Scale size={14} className="text-accent" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-foreground">
            Rubric Scores
          </div>
          <div className="text-[11px] text-muted-foreground">
            Score each rubric separately; the weighted total previews the final
            grade
          </div>
        </div>
        {hasFinal && (
          <span
            className="shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold bg-primary/10 text-primary ring-1 ring-primary/20"
            title="Weighted final grade across all rubrics (used for export)"
          >
            Final {finalGrade.grade} · {finalGrade.score}/10
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
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <Scale size={18} className="text-muted-foreground mx-auto mb-2" />
            <p className="text-sm font-medium text-foreground">No rubrics</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Add rubrics on the module page first, then score them here.
            </p>
          </div>
        ) : (
          rubrics.map((r) => {
            const s = scores[r.id];
            const busy = scoringId === r.id;
            return (
              <div
                key={r.id}
                className="flex items-center gap-3 rounded-md bg-secondary/40 border border-border px-3 py-2.5"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-foreground truncate">
                    {r.name || r.file_name || 'Rubric'}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    {r.weight != null ? `weight ${r.weight}` : 'no weight set'}
                  </div>
                </div>
                {s && s.score != null ? (
                  <>
                    <div className="shrink-0 text-right">
                      <div className="text-sm font-bold text-foreground">
                        {s.score}/10
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {s.teacher_score != null
                          ? `teacher · AI was ${s.ai_score}`
                          : `AI · grade ${s.grade}`}
                      </div>
                    </div>
                    <input
                      type="number"
                      min={0}
                      max={10}
                      step={0.5}
                      defaultValue={s.teacher_score ?? ''}
                      placeholder="set"
                      onBlur={(e) => handleOverride(r, e.target.value)}
                      title="Teacher override (blank = use AI score)"
                      className="shrink-0 w-14 bg-background border border-border rounded-md px-2 py-1 text-xs text-foreground text-center focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                    />
                  </>
                ) : (
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    not scored
                  </span>
                )}
                <button
                  onClick={() => handleGenerate(r)}
                  disabled={busy}
                  className="shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-primary text-primary-foreground text-[11px] font-semibold hover:bg-primary/90 transition-colors cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {busy ? (
                    <span className="w-3 h-3 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  ) : s ? (
                    <RefreshCw size={11} />
                  ) : (
                    <Sparkles size={11} />
                  )}
                  {busy ? 'Scoring…' : s ? 'Re-score' : 'Score'}
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
