'use client';

import { Loader2 } from 'lucide-react';

export default function FinalizeConfirmDialog({
  open,
  hasOverlapWarning = false,
  loading = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4">
      <div
        className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="finalize-dialog-title"
      >
        <h3
          id="finalize-dialog-title"
          className="text-base font-semibold text-foreground"
        >
          Finalize assessment?
        </h3>
        <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
          The form will be locked from further AI changes. This saves a
          read-only final snapshot to the assessment record.
        </p>
        {hasOverlapWarning && (
          <p className="mt-3 text-sm text-amber-400 leading-relaxed">
            High-confidence overlap indicators exist for this student. Review
            overlaps manually before finalizing.
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Finalizing…
              </>
            ) : (
              'Finalize and lock'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
