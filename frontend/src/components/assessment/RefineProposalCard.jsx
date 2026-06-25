'use client';

import { CheckCircle2, X, XCircle } from 'lucide-react';

export default function RefineProposalCard({
  proposal,
  onAccept,
  onReject,
  accepting = false,
  rejecting = false,
  disabled = false,
}) {
  if (!proposal) return null;

  const meta = proposal.metadata || {};
  const status = meta.status || 'pending';
  const changes = meta.proposed_changes || proposal.proposed_changes || [];
  const isPending = status === 'pending';

  return (
    <div
      className={`rounded-lg border p-3 space-y-3 ${
        status === 'applied'
          ? 'border-emerald-500/30 bg-emerald-500/5'
          : status === 'rejected' || status === 'superseded'
            ? 'border-border bg-secondary/30 opacity-70'
            : 'border-primary/30 bg-primary/5'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-primary">
            Refinement proposal
          </p>
          <p className="text-xs text-foreground mt-1 leading-relaxed">
            {proposal.content}
          </p>
        </div>
        {status === 'applied' && (
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 shrink-0">
            <CheckCircle2 size={12} />
            Applied
          </span>
        )}
        {status === 'rejected' && (
          <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground shrink-0">
            <XCircle size={12} />
            Rejected
          </span>
        )}
      </div>

      {changes.length > 0 ? (
        <div className="space-y-2">
          {changes.map((c) => (
            <div
              key={c.criterion_key}
              className="rounded-md bg-background/60 border border-border px-3 py-2 text-[11px]"
            >
              <p className="font-semibold text-foreground">
                {c.criterion_name}
              </p>
              <p className="text-muted-foreground mt-0.5">
                Score:{' '}
                <span className="font-mono">
                  {c.before_score ?? '—'} → {c.after_score ?? '—'}
                </span>
                /10
              </p>
              {c.after_comment && (
                <p className="text-muted-foreground mt-1 line-clamp-3">
                  {c.after_comment}
                </p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground italic">
          No criterion score changes in this proposal.
        </p>
      )}

      {meta.summary_proposed && (
        <div className="text-[11px] text-muted-foreground border-t border-border/50 pt-2">
          <span className="font-semibold text-foreground">Summary: </span>
          {meta.summary_proposed}
        </div>
      )}

      {isPending && !disabled && (
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={() => onAccept?.(meta.proposal_id || proposal.id)}
            disabled={accepting || rejecting || changes.length === 0}
            className="inline-flex items-center gap-1 flex-1 justify-center px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            <CheckCircle2 size={12} />
            {accepting ? 'Applying…' : 'Accept'}
          </button>
          <button
            type="button"
            onClick={() => onReject?.(meta.proposal_id || proposal.id)}
            disabled={accepting || rejecting}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md border border-border text-xs text-muted-foreground hover:text-foreground hover:bg-secondary disabled:opacity-50"
          >
            <X size={12} />
            {rejecting ? '…' : 'Reject'}
          </button>
        </div>
      )}
    </div>
  );
}
