'use client';

import { useCallback, useRef, useState } from 'react';
import { Link2, Link2Off } from 'lucide-react';
import HighlightedPassage from '@/components/overlaps/HighlightedPassage';

function DocumentPanel({ title, fileName, text, scrollRef, onScroll }) {
  return (
    <div className="flex flex-col min-h-0 rounded-lg bg-card border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border bg-secondary/20 shrink-0">
        <p className="text-xs font-semibold text-foreground">{title}</p>
        <p className="text-[11px] text-muted-foreground font-mono truncate">
          {fileName}
        </p>
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="overflow-y-auto max-h-[70vh] p-4"
      >
        <HighlightedPassage text={text} />
      </div>
    </div>
  );
}

export default function SyncedDocumentViewer({
  leftTitle,
  leftFileName,
  leftText,
  rightTitle,
  rightFileName,
  rightText,
}) {
  const [syncScroll, setSyncScroll] = useState(true);
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const ignoreLeftScrollRef = useRef(false);
  const ignoreRightScrollRef = useRef(false);

  const syncFromTo = useCallback((source, target) => {
    if (!syncScroll || !source || !target) return;
    const sourceMax = source.scrollHeight - source.clientHeight;
    const targetMax = target.scrollHeight - target.clientHeight;
    if (sourceMax <= 0 || targetMax <= 0) return;

    const ratio = source.scrollTop / sourceMax;
    const next = ratio * targetMax;
    if (Math.abs(target.scrollTop - next) < 1) return;
    target.scrollTop = next;
  }, [syncScroll]);

  const onLeftScroll = useCallback(() => {
    if (ignoreLeftScrollRef.current) {
      ignoreLeftScrollRef.current = false;
      return;
    }
    ignoreRightScrollRef.current = true;
    syncFromTo(leftRef.current, rightRef.current);
  }, [syncFromTo]);

  const onRightScroll = useCallback(() => {
    if (ignoreRightScrollRef.current) {
      ignoreRightScrollRef.current = false;
      return;
    }
    ignoreLeftScrollRef.current = true;
    syncFromTo(rightRef.current, leftRef.current);
  }, [syncFromTo]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Full document view — overlapping text highlighted in amber. Scroll panes
          can be synced with the toggle.
        </p>
        <button
          type="button"
          onClick={() => setSyncScroll((v) => !v)}
          className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            syncScroll
              ? 'border-primary/40 bg-primary/10 text-primary'
              : 'border-border bg-secondary text-muted-foreground hover:text-foreground'
          }`}
          aria-pressed={syncScroll}
        >
          {syncScroll ? <Link2 size={14} /> : <Link2Off size={14} />}
          {syncScroll ? 'Synced scrolling on' : 'Synced scrolling off'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        <DocumentPanel
          title={leftTitle}
          fileName={leftFileName}
          text={leftText}
          scrollRef={leftRef}
          onScroll={onLeftScroll}
        />
        <DocumentPanel
          title={rightTitle}
          fileName={rightFileName}
          text={rightText}
          scrollRef={rightRef}
          onScroll={onRightScroll}
        />
      </div>
    </div>
  );
}
