'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { FileText, Loader2 } from 'lucide-react';
import { getModuleOverlapSignal } from '@/lib/api/modulesApi';
import { APP_PATHS } from '@/lib/routes';
import OverlapStatusBadge, {
  IntegrityTypeBadge,
} from '@/components/overlaps/OverlapStatusBadge';
import OverlapDetailViewer from '@/components/overlaps/OverlapDetailViewer';
import {
  buildOverlapMetricRows,
  integrityAccentClass,
} from '@/components/overlaps/OverlapSignalMetrics';

function integrityTitle(data) {
  const type = data.integrity_type || 'student_plagiarism';
  if (type === 'ai') return 'AI-generated content';
  return 'Overlap signal';
}

function detectionLabel(method) {
  if (!method) return null;
  const labels = {
    direct_comparison: 'Direct compare',
    near_duplicate: 'Near-duplicate',
    direct_plus_ai: 'Direct + AI',
    ai_full_document: 'AI doc review',
    ai_plagiarism: 'AI plagiarism',
    ai_excerpt_chunks: 'AI excerpts',
    classifier_roberta: 'AI classifier',
    heuristic_ai: 'Heuristic AI',
  };
  return labels[method] || method.replace(/_/g, ' ');
}

function SidebarStat({ label, value, tone = 'neutral' }) {
  const tones = {
    violet: 'border-violet-500/25 bg-violet-500/[0.06]',
    amber: 'border-amber-500/25 bg-amber-500/[0.06]',
    neutral: 'border-border bg-secondary/30',
  };
  return (
    <div
      className={`rounded-md border px-2 py-1.5 text-center ${tones[tone] ?? tones.neutral}`}
    >
      <p className="text-sm font-semibold font-mono tabular-nums text-foreground leading-none">
        {value}
      </p>
      <p className="text-[9px] uppercase tracking-wide text-muted-foreground mt-1 leading-tight">
        {label}
      </p>
    </div>
  );
}

function StudentRow({ name, fileName }) {
  return (
    <div className="min-w-0 rounded-md border border-border bg-secondary/20 px-2.5 py-2">
      <p className="text-xs font-semibold text-foreground truncate">{name}</p>
      <p className="text-[10px] text-muted-foreground font-mono truncate flex items-center gap-1 mt-0.5">
        <FileText size={10} className="shrink-0 opacity-70" />
        {fileName}
      </p>
    </div>
  );
}

export default function OverlapDetailPage() {
  const { moduleId, signalId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getModuleOverlapSignal(moduleId, signalId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [moduleId, signalId]);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <p className="text-sm text-red-400">{error || 'Overlap not found'}</p>
    );
  }

  const integrityType = data.integrity_type || 'student_plagiarism';
  const singlePane = data.view_mode === 'single' || integrityType === 'ai';
  const accent = integrityAccentClass(integrityType);
  const metricRows = buildOverlapMetricRows(data);

  const leftText =
    data.document_a || data.passage_a || data.snippet || 'No document text available.';
  const rightText = data.document_b || data.passage_b || 'No document text available.';

  return (
    <div className="flex flex-col min-h-[calc(100vh-7rem)] -my-2">
      <div className="grid grid-cols-1 lg:grid-cols-[15.5rem_minmax(0,1fr)] xl:grid-cols-[17rem_minmax(0,1fr)] gap-4 flex-1 min-h-0">
        <aside
          className={`lg:sticky lg:top-4 self-start rounded-lg border border-border bg-card border-l-[3px] ${accent} p-3 space-y-3 text-sm`}
        >
          <Link
            href={APP_PATHS.moduleOverlaps(moduleId)}
            className="inline-block text-xs text-primary hover:text-primary/80"
          >
            ← All overlaps
          </Link>

          <div>
            <h1 className="text-base font-bold text-foreground leading-snug">
              {integrityTitle(data)}
            </h1>
            {!singlePane && (
              <p className="text-[11px] text-muted-foreground mt-1 leading-snug">
                {data.student_a_name}
                <span className="mx-1 opacity-50">·</span>
                {data.student_b_name}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-1">
            <IntegrityTypeBadge type={integrityType} />
            <OverlapStatusBadge kind={data.status} />
            {data.scope && <OverlapStatusBadge kind={data.scope} />}
            {data.detection_method && (
              <span className="text-[9px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-secondary text-muted-foreground ring-1 ring-border">
                {detectionLabel(data.detection_method)}
              </span>
            )}
            {data.ai_verified && (
              <span className="text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20">
                AI verified
              </span>
            )}
          </div>

          {metricRows.length > 0 && (
            <div className="grid grid-cols-2 gap-1.5">
              {metricRows.map((row) => (
                <SidebarStat
                  key={row.key ?? row.label}
                  label={row.label}
                  value={row.value}
                  tone={
                    row.key === 'ai' || row.key === 'peak'
                      ? 'violet'
                      : row.key === 'matches' || row.key === 'overlap'
                        ? 'amber'
                        : 'neutral'
                  }
                />
              ))}
            </div>
          )}

          {data.metrics_summary && (
            <p className="text-[11px] text-muted-foreground leading-snug line-clamp-3">
              {data.metrics_summary}
            </p>
          )}

          <div className="space-y-1.5">
            <StudentRow name={data.student_a_name} fileName={data.evidence_a_name} />
            {!singlePane && (
              <StudentRow name={data.student_b_name} fileName={data.evidence_b_name} />
            )}
          </div>

          {data.ai_explanation && (
            <div className="rounded-md border border-border bg-secondary/20 px-2.5 py-2">
              <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
                Note
              </p>
              <p className="text-[11px] text-foreground leading-snug line-clamp-4">
                {data.ai_explanation}
              </p>
            </div>
          )}
        </aside>

        <main className="flex flex-col min-h-0 min-w-0">
          <OverlapDetailViewer
            fillHeight
            integrityType={integrityType}
            flags={data.flags}
            singlePane={singlePane}
            leftTitle={data.student_a_name}
            leftFileName={data.evidence_a_name}
            leftText={leftText}
            rightTitle={data.student_b_name}
            rightFileName={data.evidence_b_name}
            rightText={rightText}
          />
        </main>
      </div>
    </div>
  );
}
