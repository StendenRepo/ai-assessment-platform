'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Link2, Link2Off } from 'lucide-react';
import AnnotatedDocument, {
  buildStudentMatchLegend,
  matchAnchorId,
  matchStyle,
} from '@/components/overlaps/AnnotatedDocument';

function DocumentPanel({
  title,
  fileName,
  text,
  flags,
  pane,
  scrollRef,
  onScroll,
  activeMatchId,
  hoveredMatchId,
  onMatchActivate,
  onMatchHover,
  inlineBadges,
  dimInactive,
  fillHeight = false,
}) {
  return (
    <div
      className={`flex flex-col min-h-0 rounded-lg bg-card border border-border overflow-hidden ${
        fillHeight ? 'h-full' : ''
      }`}
    >
      <div className="px-3 py-2 border-b border-border bg-secondary/15 shrink-0">
        <p className="text-xs font-semibold text-foreground truncate">
          {title}
        </p>
        <p className="text-[10px] text-muted-foreground font-mono truncate">
          {fileName}
        </p>
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className={`overflow-y-auto p-3 scroll-smooth ${
          fillHeight ? 'flex-1 min-h-0' : 'max-h-[min(70vh,42rem)]'
        }`}
      >
        <AnnotatedDocument
          text={text}
          flags={flags}
          pane={pane}
          activeMatchId={activeMatchId}
          hoveredMatchId={hoveredMatchId}
          onMatchActivate={onMatchActivate}
          onMatchHover={onMatchHover}
          inlineBadges={inlineBadges}
          dimInactive={dimInactive}
        />
      </div>
    </div>
  );
}

function scrollPaneToMatch(scrollEl, pane, matchId) {
  if (!scrollEl || matchId == null) return;
  const anchor = scrollEl.querySelector(`#${matchAnchorId(pane, matchId)}`);
  if (!anchor) return;
  const containerTop = scrollEl.getBoundingClientRect().top;
  const anchorTop = anchor.getBoundingClientRect().top;
  const offset = anchorTop - containerTop + scrollEl.scrollTop - 56;
  scrollEl.scrollTo({ top: Math.max(0, offset), behavior: 'smooth' });
}

export default function FlaggedDocumentViewer({
  viewMode = 'side_by_side',
  integrityType = 'student_plagiarism',
  flags = [],
  leftTitle,
  leftFileName,
  leftText,
  rightTitle,
  rightFileName,
  rightText,
  initialMatchId = null,
  inlineBadges = true,
  compactChrome = false,
  fillHeight = false,
}) {
  const [syncScroll, setSyncScroll] = useState(true);
  const [activeMatchId, setActiveMatchId] = useState(initialMatchId);
  const [hoveredMatchId, setHoveredMatchId] = useState(null);
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const ignoreLeftScrollRef = useRef(false);
  const ignoreRightScrollRef = useRef(false);

  const singlePane = viewMode === 'single' || integrityType === 'ai';
  const studentMatches = buildStudentMatchLegend(flags);

  useEffect(() => {
    if (initialMatchId == null) return;
    setActiveMatchId(initialMatchId);
    const t = setTimeout(() => {
      scrollPaneToMatch(leftRef.current, 'left', initialMatchId);
      if (!singlePane) {
        scrollPaneToMatch(rightRef.current, 'right', initialMatchId);
      }
    }, 80);
    return () => clearTimeout(t);
  }, [initialMatchId, singlePane]);

  const scrollToMatch = useCallback(
    (matchId) => {
      if (matchId == null) return;
      setActiveMatchId(matchId);
      scrollPaneToMatch(leftRef.current, 'left', matchId);
      if (!singlePane) {
        scrollPaneToMatch(rightRef.current, 'right', matchId);
      }
    },
    [singlePane]
  );

  const navigateMatch = useCallback(
    (direction) => {
      if (!studentMatches.length) return;
      const ids = studentMatches.map((m) => m.matchId);
      const currentIndex =
        activeMatchId != null ? ids.indexOf(activeMatchId) : -1;
      let nextIndex;
      if (direction < 0) {
        nextIndex = currentIndex <= 0 ? ids.length - 1 : currentIndex - 1;
      } else {
        nextIndex =
          currentIndex < 0 || currentIndex >= ids.length - 1
            ? 0
            : currentIndex + 1;
      }
      scrollToMatch(ids[nextIndex]);
    },
    [activeMatchId, scrollToMatch, studentMatches]
  );

  const syncFromTo = useCallback(
    (source, target, targetPane) => {
      if (!syncScroll || !source || !target) return;
      const targetAnchor =
        activeMatchId != null
          ? target.querySelector(`#${matchAnchorId(targetPane, activeMatchId)}`)
          : null;
      if (targetAnchor) {
        targetAnchor.scrollIntoView({ block: 'center', behavior: 'auto' });
        return;
      }
      const sourceMax = source.scrollHeight - source.clientHeight;
      const targetMax = target.scrollHeight - target.clientHeight;
      if (sourceMax <= 0 || targetMax <= 0) return;
      target.scrollTop = (source.scrollTop / sourceMax) * targetMax;
    },
    [activeMatchId, syncScroll]
  );

  const onLeftScroll = useCallback(() => {
    if (ignoreLeftScrollRef.current) {
      ignoreLeftScrollRef.current = false;
      return;
    }
    ignoreRightScrollRef.current = true;
    syncFromTo(leftRef.current, rightRef.current, 'right');
  }, [syncFromTo]);

  const onRightScroll = useCallback(() => {
    if (ignoreRightScrollRef.current) {
      ignoreRightScrollRef.current = false;
      return;
    }
    ignoreLeftScrollRef.current = true;
    syncFromTo(rightRef.current, leftRef.current, 'left');
  }, [syncFromTo]);

  return (
    <div
      className={`${fillHeight ? 'flex flex-col flex-1 min-h-0 gap-2' : 'space-y-3'}`}
    >
      {!compactChrome && (
        <p className="text-xs text-muted-foreground shrink-0">
          {singlePane
            ? 'Highlighted passages in the full submission.'
            : 'Scroll either pane — matching numbers use the same colour on both sides.'}
        </p>
      )}

      {!singlePane && studentMatches.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 shrink-0">
          {!inlineBadges && (
            <div className="flex flex-wrap gap-1 min-w-0">
              {studentMatches.map((entry) => {
                const palette = matchStyle(entry.matchId);
                const isActive = activeMatchId === entry.matchId;
                return (
                  <button
                    key={entry.matchId}
                    type="button"
                    onClick={() => scrollToMatch(entry.matchId)}
                    className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
                      isActive
                        ? 'border-primary/50 bg-primary/10 text-foreground'
                        : 'border-border bg-secondary/25 text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <span
                      className={`flex h-3.5 w-3.5 items-center justify-center rounded-full border text-[8px] font-bold ${palette.swatch}`}
                    >
                      {entry.matchId}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
          <div className="flex items-center gap-1.5 ml-auto shrink-0">
            <div className="inline-flex items-center gap-0.5 rounded-md border border-border bg-secondary/30 px-0.5 py-0.5">
              <button
                type="button"
                onClick={() => navigateMatch(-1)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
                aria-label="Previous match"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-[10px] font-medium text-foreground px-1.5 min-w-[3.5rem] text-center">
                {activeMatchId != null
                  ? `${activeMatchId}/${studentMatches.length}`
                  : studentMatches.length}
              </span>
              <button
                type="button"
                onClick={() => navigateMatch(1)}
                className="p-1 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
                aria-label="Next match"
              >
                <ChevronRight size={14} />
              </button>
            </div>
            <button
              type="button"
              onClick={() => setSyncScroll((v) => !v)}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium border transition-colors ${
                syncScroll
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border bg-secondary text-muted-foreground hover:text-foreground'
              }`}
              aria-pressed={syncScroll}
            >
              {syncScroll ? <Link2 size={12} /> : <Link2Off size={12} />}
              Sync
            </button>
          </div>
        </div>
      )}

      {singlePane ? (
        <DocumentPanel
          title={leftTitle}
          fileName={leftFileName}
          text={leftText}
          flags={flags}
          pane="left"
          activeMatchId={activeMatchId}
          hoveredMatchId={hoveredMatchId}
          onMatchActivate={scrollToMatch}
          onMatchHover={setHoveredMatchId}
          inlineBadges={inlineBadges}
          dimInactive={!!activeMatchId}
          fillHeight={fillHeight}
        />
      ) : (
        <div
          className={`grid grid-cols-1 lg:grid-cols-2 gap-3 min-h-0 ${
            fillHeight ? 'flex-1' : ''
          }`}
        >
          <DocumentPanel
            title={leftTitle}
            fileName={leftFileName}
            text={leftText}
            flags={flags}
            pane="left"
            scrollRef={leftRef}
            onScroll={onLeftScroll}
            activeMatchId={activeMatchId}
            hoveredMatchId={hoveredMatchId}
            onMatchActivate={scrollToMatch}
            onMatchHover={setHoveredMatchId}
            inlineBadges={inlineBadges}
            dimInactive={!!activeMatchId}
            fillHeight={fillHeight}
          />
          <DocumentPanel
            title={rightTitle}
            fileName={rightFileName}
            text={rightText}
            flags={flags}
            pane="right"
            scrollRef={rightRef}
            onScroll={onRightScroll}
            activeMatchId={activeMatchId}
            hoveredMatchId={hoveredMatchId}
            onMatchActivate={scrollToMatch}
            onMatchHover={setHoveredMatchId}
            inlineBadges={inlineBadges}
            dimInactive={!!activeMatchId}
            fillHeight={fillHeight}
          />
        </div>
      )}
    </div>
  );
}
