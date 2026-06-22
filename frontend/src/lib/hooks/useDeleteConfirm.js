'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';

export function useDeleteConfirm({ onDelete, onDeleted, onError }) {
  const [pendingItem, setPendingItem] = useState(null);

  const requestDelete = (item) => {
    if (!item) return;
    setPendingItem(item);
  };

  const cancelDelete = () => {
    setPendingItem(null);
  };

  const confirmDelete = async () => {
    if (!pendingItem) return;
    try {
      await onDelete(pendingItem);
      onDeleted?.(pendingItem);
      setPendingItem(null);
    } catch (err) {
      onError?.(err);
      setPendingItem(null);
    }
  };

  return {
    pendingItem,
    requestDelete,
    cancelDelete,
    confirmDelete,
  };
}

export function ModuleDeleteConfirmDialog({
  open,
  title = 'Delete module',
  label,
  message,
  warningTitle = 'This action cannot be undone. It will permanently delete:',
  warningItems = [
    'The module and all its settings',
    'All groups and students in this module',
    'All uploaded evidence files',
    'The rubric file (if any)',
  ],
  confirmLabel = 'Delete module',
  loading = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === 'Escape') onCancel?.();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="relative w-full max-w-md mx-4 rounded-xl bg-card border border-border shadow-2xl p-6 space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <div className="shrink-0 w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
            <AlertTriangle size={18} className="text-red-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {message || (
                <>
                  Are you sure you want to delete{' '}
                  <span className="font-medium text-foreground">{label}</span>?
                </>
              )}
            </p>
          </div>
        </div>

        {Array.isArray(warningItems) && warningItems.length > 0 && (
          <div className="rounded-lg bg-red-500/5 border border-red-500/20 px-4 py-3 text-xs text-red-400 space-y-1">
            <p className="font-medium">{warningTitle}</p>
            <ul className="list-disc list-inside space-y-0.5 text-red-400/80">
              {warningItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-1">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-muted-foreground bg-secondary hover:bg-secondary/80 border border-border transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-700 transition-colors disabled:opacity-60 flex items-center gap-2"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Trash2 size={14} />
            )}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
