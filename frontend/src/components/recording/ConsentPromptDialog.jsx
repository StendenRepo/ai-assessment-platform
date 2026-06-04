'use client';

import { useState } from 'react';
import { Mic, CheckCircle2, XCircle } from 'lucide-react';

/**
 * Per-recording consent prompt (FR-06, G2-137).
 *
 * Shown each time the teacher starts a recording. The student states their name
 * and says "I consent" at the start of the audio; the teacher confirms here.
 * Accept -> recording begins. Decline -> the recording is cancelled.
 */
export default function ConsentPromptDialog({ onAccept, onDecline }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function handleAccept() {
    setSaving(true);
    setError(null);
    try {
      await onAccept();
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
            <Mic size={16} className="text-primary" />
          </div>
          <h3 className="text-base font-bold text-foreground">
            Confirm recording consent
          </h3>
        </div>

        <p className="text-sm text-muted-foreground mb-2">
          Ask the student to state their full name and say{' '}
          <span className="font-semibold text-foreground">
            &ldquo;I consent&rdquo;
          </span>{' '}
          before you begin.
        </p>
        <p className="text-xs text-muted-foreground mb-5">
          Did the student consent to this recording?
        </p>

        {error && <p className="text-xs text-red-400 mb-3">{error}</p>}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onDecline}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-red-500/10 text-red-400 ring-1 ring-red-500/20 text-sm font-semibold hover:bg-red-500/20 transition-colors disabled:opacity-50"
          >
            <XCircle size={14} /> Decline
          </button>
          <button
            onClick={handleAccept}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20 text-sm font-semibold hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
          >
            <CheckCircle2 size={14} />{' '}
            {saving ? 'Starting…' : 'Accept & record'}
          </button>
        </div>
      </div>
    </div>
  );
}
