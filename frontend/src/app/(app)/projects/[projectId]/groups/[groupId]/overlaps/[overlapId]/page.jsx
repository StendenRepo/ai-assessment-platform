'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { overlapApi } from '@/lib/overlapApi';
import HighlightedPassage from '@/components/overlaps/HighlightedPassage';
import OverlapStatusBadge from '@/components/overlaps/OverlapStatusBadge';

export default function OverlapDetailPage() {
  const { projectId, groupId, overlapId } = useParams();
  const [item, setItem] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    overlapApi
      .detail(projectId, groupId, overlapId)
      .then(setItem)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectId, groupId, overlapId]);

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="space-y-4">
        <Link
          href={`/projects/${projectId}/groups/${groupId}/overlaps`}
          className="text-xs text-muted-foreground hover:text-primary transition-colors"
        >
          ← All overlaps
        </Link>
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-3">
          {error || 'Overlap not found'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/projects/${projectId}/groups/${groupId}/overlaps`}
          className="text-xs text-muted-foreground hover:text-primary transition-colors"
        >
          ← All overlaps
        </Link>
        <h1 className="text-2xl font-bold text-foreground mt-2">
          Side-by-side comparison
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {item.student_a_name} and {item.student_b_name}
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <OverlapStatusBadge
            status={item.status}
            percent={item.similarity_percent}
          />
          <span className="text-xs text-muted-foreground capitalize">
            {item.status} match
          </span>
          {item.scope === 'cross_group' && (
            <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20">
              Cross-group · {item.group_a_name} ↔ {item.group_b_name}
            </span>
          )}
          {item.scope !== 'cross_group' && (
            <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide bg-secondary text-muted-foreground ring-1 ring-border">
              Within group
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {[
          {
            name: item.student_a_name,
            file: item.file_a,
            passage: item.passage_a,
          },
          {
            name: item.student_b_name,
            file: item.file_b,
            passage: item.passage_b,
          },
        ].map((side) => (
          <div
            key={side.name}
            className="rounded-lg bg-card border border-border overflow-hidden flex flex-col min-h-[280px]"
          >
            <div className="px-5 py-4 border-b border-border bg-secondary/30">
              <p className="text-sm font-semibold text-foreground">{side.name}</p>
              <p className="text-xs text-muted-foreground font-mono mt-0.5 truncate">
                {side.file}
              </p>
            </div>
            <div className="p-5 flex-1 overflow-y-auto max-h-[420px] bg-background/50">
              <HighlightedPassage text={side.passage} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
