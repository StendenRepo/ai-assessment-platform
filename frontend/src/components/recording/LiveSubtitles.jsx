'use client';

import { Captions } from 'lucide-react';

/**
 * Rolling live-subtitle caption shown under the recording controls (FR-06).
 *
 * Displays the latest transient partial text from the live WebSocket. This is
 * NEVER the official transcript and is never persisted — the label makes that
 * explicit. The parent hides this entirely (silently) if the live path fails,
 * so the recording is never blocked by a subtitle error.
 */
export default function LiveSubtitles({ text }) {
  return (
    <div className="rounded-md bg-secondary/60 border border-border px-3 py-2">
      <div className="flex items-center gap-1.5 mb-1">
        <Captions size={11} className="text-muted-foreground" />
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Live subtitles
        </span>
        <span className="text-[9px] text-muted-foreground/70">· not saved</span>
      </div>
      <p
        className="text-xs text-foreground leading-relaxed min-h-[1.25rem]"
        aria-live="polite"
      >
        {text || (
          <span className="text-muted-foreground italic">Listening…</span>
        )}
      </p>
    </div>
  );
}
