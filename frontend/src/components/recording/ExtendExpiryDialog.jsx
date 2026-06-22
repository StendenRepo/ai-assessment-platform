'use client';

import { useState } from 'react';
import { CalendarClock } from 'lucide-react';
import { UI_STATUS_LABELS } from '@/lib/uiStatusLabels';

/**
 * Modal to extend a recording's deletion date (GDPR-capped).
 * A non-empty reason is required; days are capped 1–90 by the backend.
 */
export default function ExtendExpiryDialog({ recording, onClose, onSubmit }) {
  const [reason, setReason] = useState('');
  const [extraDays, setExtraDays] = useState(90);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const remaining = Math.max(2 - (recording.extension_count ?? 0), 0);

  async function handleSubmit() {
    if (!reason.trim()) {
      setError('A reason is required.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ reason: reason.trim(), extraDays: Number(extraDays) });
      onClose();
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl p-6 max-w-md w-full shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center">
            <CalendarClock size={16} className="text-primary" />
          </div>
          <h3 className="text-base font-bold text-foreground">
            Extend deletion date
          </h3>
        </div>

        <p className="text-xs text-muted-foreground mb-4">
          Extending “{recording.display_name}”. {remaining} extension
          {remaining !== 1 ? 's' : ''} remaining (max 2, up to 90 days each).
        </p>

        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
          Additional days (max 90)
        </label>
        <input
          type="number"
          min={1}
          max={90}
          value={extraDays}
          onChange={(e) => setExtraDays(e.target.value)}
          className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground font-mono mb-4 focus:outline-none focus:ring-2 focus:ring-ring"
        />

        <label className="block text-xs font-medium text-muted-foreground mb-1.5">
          Reason (required)
        </label>
        <textarea
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why is the recording being kept longer?"
          className="w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring mb-2"
        />

        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

        <div className="flex gap-3 justify-end mt-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || remaining === 0}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {saving ? UI_STATUS_LABELS.saving : 'Extend'}
          </button>
        </div>
      </div>
    </div>
  );
}
