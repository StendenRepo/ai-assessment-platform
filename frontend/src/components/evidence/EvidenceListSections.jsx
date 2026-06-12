'use client';

import EvidenceListItem from '@/components/evidence/EvidenceListItem';

export default function EvidenceListSections({
  evidenceLoading = false,
  allCount = 0,
  sections = [],
  getItemCanPreview,
  onPreview,
  onDownload,
  onDelete,
  emptyText = 'No evidence uploaded yet.',
}) {
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="p-5 space-y-2">
        <p className="text-xs font-semibold text-foreground uppercase tracking-wide">
          Evidence ({allCount})
        </p>

        {evidenceLoading ? (
          <div className="flex justify-center py-4">
            <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : allCount === 0 ? (
          <p className="text-xs text-muted-foreground py-2">{emptyText}</p>
        ) : (
          sections.map((section) => (
            <div
              key={section.key}
              className={
                section.dividerTop
                  ? 'pt-3 mt-2 border-t border-border space-y-2'
                  : 'pt-1 space-y-2'
              }
            >
              {section.title && (
                <p className="text-[11px] font-semibold text-foreground uppercase tracking-wide">
                  {section.title} ({section.items.length})
                </p>
              )}

              {section.items.length === 0 ? (
                <p className="text-xs text-muted-foreground py-1">
                  {section.emptyText}
                </p>
              ) : (
                section.items.map((evidence) => (
                  <EvidenceListItem
                    key={evidence.id}
                    evidence={evidence}
                    canPreview={getItemCanPreview(evidence)}
                    onPreview={onPreview}
                    onDownload={onDownload}
                    onDelete={onDelete}
                  />
                ))
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
