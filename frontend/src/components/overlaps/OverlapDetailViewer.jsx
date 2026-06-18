'use client';

import { useCallback, useRef, useState } from 'react';
import { BookOpen, Layers } from 'lucide-react';
import OverlapMatchReview, { buildMatchEntries } from '@/components/overlaps/OverlapMatchReview';
import FlaggedDocumentViewer from '@/components/overlaps/FlaggedDocumentViewer';

const TABS = [
  { id: 'matches', label: 'Matched passages', icon: Layers },
  { id: 'documents', label: 'Full documents', icon: BookOpen },
];

export default function OverlapDetailViewer({
  integrityType,
  flags,
  singlePane,
  leftTitle,
  leftFileName,
  leftText,
  rightTitle,
  rightFileName,
  rightText,
  fillHeight = false,
}) {
  const { student } = buildMatchEntries(flags);
  const [tab, setTab] = useState(student.length ? 'matches' : 'documents');
  const [scrollToMatchId, setScrollToMatchId] = useState(null);
  const [docViewerKey, setDocViewerKey] = useState(0);
  const docViewerRef = useRef(null);

  const openInDocument = useCallback((matchId) => {
    setTab('documents');
    setScrollToMatchId(matchId);
    setDocViewerKey((k) => k + 1);
  }, []);

  const handleTabChange = (id) => {
    setTab(id);
    if (id === 'matches') setScrollToMatchId(null);
  };

  return (
    <div className={`flex flex-col min-h-0 ${fillHeight ? 'flex-1 h-full' : 'space-y-4'}`}>
      <div className="inline-flex shrink-0 rounded-lg border border-border bg-secondary/20 p-0.5 mb-3">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => handleTabChange(id)}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              tab === id
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Icon size={13} />
            {label}
            {id === 'matches' && student.length > 0 && (
              <span className="text-[10px] font-mono text-muted-foreground">
                {student.length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className={`min-h-0 ${fillHeight ? 'flex-1 flex flex-col' : ''}`}>
      {tab === 'matches' ? (
        <OverlapMatchReview
          flags={flags}
          leftLabel={leftTitle}
          rightLabel={rightTitle}
          singlePane={singlePane}
          onViewInDocument={openInDocument}
          compact={fillHeight}
        />
      ) : (
        <div ref={docViewerRef} className={fillHeight ? 'flex-1 flex flex-col min-h-0' : ''}>
          <FlaggedDocumentViewer
            key={docViewerKey}
            viewMode={singlePane ? 'single' : 'side_by_side'}
            integrityType={integrityType}
            flags={flags}
            leftTitle={leftTitle}
            leftFileName={leftFileName}
            leftText={leftText}
            rightTitle={rightTitle}
            rightFileName={rightFileName}
            rightText={rightText}
            initialMatchId={scrollToMatchId}
            inlineBadges={false}
            compactChrome
            fillHeight={fillHeight}
          />
        </div>
      )}
      </div>
    </div>
  );
}
