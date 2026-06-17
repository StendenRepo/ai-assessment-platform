'use client';

import { Square, Pause, Play } from 'lucide-react';
import LiveSubtitles from '@/components/recording/LiveSubtitles';

/**
 * Centered recording modal (FR-06).
 *
 * Shown while a recording is in progress. Holds everything in one place in the
 * middle of the screen: the elapsed timer, the transient live subtitles, and
 * the pause/resume + stop controls. There is intentionally no click-outside
 * close — the recording can only be ended via Stop & Save.
 */
export default function RecordingModal({
  elapsed,
  isPaused,
  liveText,
  liveHistory,
  liveActive,
  onPause,
  onResume,
  onStop,
}) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-card border border-border rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-5">
        <div className="flex items-center gap-2">
          <div
            className={`w-2.5 h-2.5 rounded-full ${
              isPaused ? 'bg-amber-400' : 'bg-red-500 animate-pulse'
            }`}
          />
          <span
            className={`text-xs font-semibold uppercase tracking-wide ${
              isPaused ? 'text-amber-400' : 'text-red-400'
            }`}
          >
            {isPaused ? 'Paused' : 'Recording'}
          </span>
        </div>

        <p className="text-center text-5xl font-bold font-mono text-foreground tabular-nums">
          {elapsed}
        </p>

        {liveActive ? (
          <LiveSubtitles text={liveText} history={liveHistory} />
        ) : (
          <div className="rounded-md bg-secondary/60 border border-border px-3 py-2 text-center">
            <span className="text-[11px] text-muted-foreground italic">
              Live subtitles unavailable
            </span>
          </div>
        )}

        <div className="flex gap-3">
          {isPaused ? (
            <button
              onClick={onResume}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-secondary text-foreground text-sm font-semibold hover:bg-secondary/70 transition-colors"
            >
              <Play size={14} /> Resume
            </button>
          ) : (
            <button
              onClick={onPause}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-secondary text-foreground text-sm font-semibold hover:bg-secondary/70 transition-colors"
            >
              <Pause size={14} /> Pause
            </button>
          )}
          <button
            onClick={onStop}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-foreground text-background text-sm font-semibold hover:bg-foreground/90 transition-colors"
          >
            <Square size={14} /> Stop &amp; Save
          </button>
        </div>
      </div>
    </div>
  );
}
