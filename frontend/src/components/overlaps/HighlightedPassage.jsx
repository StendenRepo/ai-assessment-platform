'use client';

export default function HighlightedPassage({ text, className = '' }) {
  if (!text) {
    return (
      <p className={`text-xs text-muted-foreground italic ${className}`}>
        No passage text available.
      </p>
    );
  }

  const parts = text.split(/(\[\[.*?\]\])/g);

  return (
    <div
      className={`text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap ${className}`}
    >
      {parts.map((part, i) =>
        part.startsWith('[[') && part.endsWith(']]') ? (
          <mark
            key={i}
            className="bg-amber-500/20 text-foreground rounded px-1 py-0.5 not-italic font-medium"
          >
            {part.slice(2, -2)}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </div>
  );
}
