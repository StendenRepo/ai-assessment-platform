'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { getModuleOverlapSignal } from '@/lib/api/modulesApi';
import { APP_PATHS } from '@/lib/routes';
import HighlightedPassage from '@/components/overlaps/HighlightedPassage';
import OverlapStatusBadge from '@/components/overlaps/OverlapStatusBadge';

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
      <p className="text-sm text-red-400">
        {error || 'Overlap not found'}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={APP_PATHS.moduleOverlaps(moduleId)}
          className="text-sm text-primary hover:text-primary/80"
        >
          ← All overlaps
        </Link>
        <h1 className="text-2xl font-bold text-foreground mt-3">
          {data.student_a_name} ↔ {data.student_b_name}
        </h1>
        <div className="flex flex-wrap gap-2 mt-2">
          <OverlapStatusBadge kind={data.status} />
          {data.scope && <OverlapStatusBadge kind={data.scope} />}
          <span className="text-xs text-muted-foreground self-center">
            {Math.round((data.confidence || 0) * 100)}% similar
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg bg-card border border-border p-5 space-y-3">
          <p className="text-xs font-semibold text-foreground">
            {data.student_a_name}
          </p>
          <p className="text-[11px] text-muted-foreground font-mono">
            {data.evidence_a_name}
          </p>
          <HighlightedPassage text={data.passage_a || data.snippet} />
        </div>
        <div className="rounded-lg bg-card border border-border p-5 space-y-3">
          <p className="text-xs font-semibold text-foreground">
            {data.student_b_name}
          </p>
          <p className="text-[11px] text-muted-foreground font-mono">
            {data.evidence_b_name}
          </p>
          <HighlightedPassage text={data.passage_b} />
        </div>
      </div>
    </div>
  );
}
