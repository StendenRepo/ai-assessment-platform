'use client';

import { useEffect, useRef } from 'react';
import Image from 'next/image';
import { XCircle } from 'lucide-react';

function buildHighlightRegex(quote) {
  const words = (quote || '').match(/\w+/g);
  if (!words || words.length === 0) return null;
  const pattern = words
    .slice(0, 40)
    .map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('[^\\w]*');
  try {
    return new RegExp(pattern);
  } catch {
    return null;
  }
}

function HighlightedText({ content, quote }) {
  const markRef = useRef(null);

  useEffect(() => {
    if (markRef.current) {
      markRef.current.scrollIntoView({ block: 'center' });
    }
  }, [content, quote]);

  const text = content || 'No extracted text available for this file.';
  const regex = quote ? buildHighlightRegex(quote) : null;
  const match = regex ? text.match(regex) : null;

  let body = text;
  if (match && match.index != null) {
    const start = match.index;
    const end = start + match[0].length;
    body = (
      <>
        {text.slice(0, start)}
        <mark
          ref={markRef}
          className="rounded bg-primary/25 text-foreground"
        >
          {text.slice(start, end)}
        </mark>
        {text.slice(end)}
      </>
    );
  }

  return (
    <pre className="h-full w-full overflow-auto rounded-lg border border-border bg-background p-4 text-left text-xs text-foreground whitespace-pre-wrap wrap-break-word">
      {body}
    </pre>
  );
}

export default function EvidencePreviewDialog({
  evidence,
  previewKind,
  basePreviewKind,
  previewUrl,
  previewContent,
  loading,
  highlightQuote,
  showImageExtractedText,
  onToggleImageExtractedText,
  onClose,
}) {
  if (!evidence && !loading) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative h-[92vh] w-full max-w-[96vw] rounded-xl border border-border bg-card shadow-xl overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-foreground">
              {evidence?.file_name ?? 'Loading preview'}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {previewKind === 'pdf'
                ? 'PDF preview'
                : previewKind === 'text'
                  ? 'Extracted text preview'
                  : 'Raw evidence preview'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {basePreviewKind === 'image' && (
              <button
                onClick={onToggleImageExtractedText}
                disabled={loading}
                className="rounded border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {showImageExtractedText
                  ? 'Back to image'
                  : 'View extracted text'}
              </button>
            )}
            <button
              onClick={onClose}
              className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            >
              <XCircle size={16} />
            </button>
          </div>
        </div>
        <div className="flex h-[calc(92vh-73px)] items-center justify-center bg-secondary/30 p-5">
          {loading ? (
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          ) : previewKind === 'image' && previewUrl ? (
            <Image
              src={previewUrl}
              alt={evidence?.file_name ?? 'Evidence preview'}
              width={1600}
              height={1200}
              unoptimized
              className="max-h-full w-auto max-w-full rounded-lg border border-border bg-background object-contain"
            />
          ) : previewKind === 'pdf' && previewUrl ? (
            <iframe
              src={previewUrl}
              title={evidence?.file_name ?? 'PDF preview'}
              className="h-full w-full rounded-lg border border-border bg-background"
            />
          ) : previewKind === 'text' ? (
            <HighlightedText content={previewContent} quote={highlightQuote} />
          ) : (
            <p className="text-sm text-muted-foreground">
              Preview unavailable.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
