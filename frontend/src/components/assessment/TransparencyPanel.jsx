'use client';

import { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, History, Loader2 } from 'lucide-react';
import { getAssessmentAuditTrail } from '@/lib/api/assessmentsApi';

const ACTION_LABELS = {
  'assessment.suggestion_overridden': 'Teacher overruled AI',
  'assessment.override_reverted': 'Reverted to AI',
  'assessment.suggestions_generated': 'AI suggestions generated',
  'assessment.chat_refine': 'Chat refinement',
  'assessment.finalized': 'Assessment finalized',
  'assessment.created': 'Assessment created',
};

function formatTimestamp(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleString('en-GB', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return ts;
  }
}

function EventDetails({ event }) {
  const d = event.details || {};
  const [open, setOpen] = useState(false);

  if (d.field === 'summary' || d.field === 'overall_grade') {
    return (
      <div className="mt-1 text-[10px] text-muted-foreground">
        <span className="font-mono">{d.field}</span>:{' '}
        <span className="line-through opacity-70">{String(d.ai ?? '—')}</span>
        {' → '}
        <span className="text-foreground">{String(d.teacher ?? '—')}</span>
      </div>
    );
  }

  if (d.criterion_key && (d.ai || d.teacher)) {
    return (
      <div className="mt-1">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground hover:text-foreground"
        >
          {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          <span className="font-mono">{d.criterion_key}</span>
        </button>
        {open && (
          <div className="mt-1 pl-3 border-l border-border space-y-1 text-[10px]">
            {d.ai && (
              <div>
                <span className="text-blue-400 font-semibold">AI</span>
                <span className="text-muted-foreground ml-1">
                  score {d.ai.score ?? '—'}
                </span>
                {d.ai.comment && (
                  <p className="text-muted-foreground mt-0.5 line-clamp-3">
                    {d.ai.comment}
                  </p>
                )}
              </div>
            )}
            {d.teacher && (
              <div>
                <span className="text-amber-400 font-semibold">Teacher</span>
                <span className="text-muted-foreground ml-1">
                  score {d.teacher.score ?? '—'}
                </span>
                {d.teacher.comment && (
                  <p className="text-muted-foreground mt-0.5 line-clamp-3">
                    {d.teacher.comment}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  if (d.changes?.length > 0) {
    return (
      <div className="mt-1 text-[10px] text-muted-foreground">
        {d.updates_applied ?? 0} criterion
        {(d.updates_applied ?? 0) !== 1 ? 's' : ''} updated via chat
      </div>
    );
  }

  if (d.criterion_key) {
    return (
      <span className="block text-muted-foreground font-mono mt-0.5 text-[10px]">
        {d.criterion_key}
      </span>
    );
  }

  return null;
}

export default function TransparencyPanel({ assessmentId, refreshKey = 0 }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!assessmentId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await getAssessmentAuditTrail(assessmentId);
        if (!cancelled) setEvents(data.slice(0, 12));
      } catch {
        if (!cancelled) setEvents([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [assessmentId, refreshKey]);

  return (
    <div className="rounded-lg bg-card border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center">
          <History size={14} className="text-muted-foreground" />
        </div>
        <div>
          <div className="text-sm font-semibold text-foreground">
            Transparency log
          </div>
          <div className="text-[11px] text-muted-foreground">
            AI vs teacher changes are recorded
          </div>
        </div>
      </div>
      <div className="p-4 max-h-64 overflow-y-auto">
        {loading ? (
          <div className="flex justify-center py-4">
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          </div>
        ) : events.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-2">
            No audit events yet
          </p>
        ) : (
          <ul className="space-y-3">
            {events.map((e, i) => (
              <li
                key={i}
                className="text-[11px] border-l-2 border-border pl-2 py-0.5"
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-foreground">
                    {ACTION_LABELS[e.action] || e.action}
                  </span>
                  <span className="text-[10px] text-muted-foreground shrink-0">
                    {formatTimestamp(e.timestamp)}
                  </span>
                </div>
                <span className="text-muted-foreground text-[10px]">
                  {e.source}
                </span>
                <EventDetails event={e} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
