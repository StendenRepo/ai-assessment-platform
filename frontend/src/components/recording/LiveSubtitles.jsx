'use client';

import { useEffect, useRef } from 'react';
import { Captions } from 'lucide-react';

/**
 * Rolling live-subtitle history shown during recording (FR-06).
 *
 * Each entry is one transient chunk from the live WebSocket — NEVER the official
 * transcript and never persisted (the label makes that explicit). The list grows
 * as the student speaks and auto-scrolls so the latest line stays in view, while
 * earlier lines remain scrollable so you can read back what was said. The parent
 * hides this entirely (silently) if the live path fails, so the recording is
 * never blocked by a subtitle error.
 *
 * `history` is an array of `{ id, text }`. `text` is the most recent line and is
 * used as a fallback before any history has accumulated.
 */
export default function LiveSubtitles({ text, history = [] }) {
  const scrollRef = useRef(null);

  // Keep the newest line in view as entries are appended.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [history]);

  const hasHistory = history.length > 0;

  return (
    <div className="rounded-md bg-secondary/60 border border-border px-3 py-2">
      <div className="flex items-center gap-1.5 mb-1">
        <Captions size={11} className="text-muted-foreground" />
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Live subtitles
        </span>
        <span className="text-[9px] text-muted-foreground/70">· not saved</span>
      </div>
      <div
        ref={scrollRef}
        className="max-h-40 overflow-y-auto space-y-1 pr-1"
        aria-live="polite"
      >
        {hasHistory ? (
          history.map((entry, index) => (
            <p
              key={entry.id}
              className={`text-xs leading-relaxed ${
                index === history.length - 1
                  ? 'text-foreground'
                  : 'text-muted-foreground'
              }`}
            >
              {entry.text}
            </p>
          ))
        ) : (
          <p className="text-xs text-foreground leading-relaxed min-h-[1.25rem]">
            {text || (
              <span className="text-muted-foreground italic">Listening…</span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
