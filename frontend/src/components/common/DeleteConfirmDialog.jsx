'use client';

export default function DeleteConfirmDialog({
  open,
  title = 'Confirm Delete',
  label,
  message,
  confirmLabel = 'Delete',
  loading = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-2xl">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="mt-3 text-sm text-muted-foreground">
          {message || (
            <>
              Are you sure you want to delete{' '}
              <span className="font-semibold text-foreground">{label}</span>?
              This action cannot be undone.
            </>
          )}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm rounded-md border border-border text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium rounded-md bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Removing...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
