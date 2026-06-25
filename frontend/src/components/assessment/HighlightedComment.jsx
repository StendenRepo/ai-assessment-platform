'use client';

/** Renders comments that may embed [[file]] markers for evidence citations. */
export default function HighlightedComment({ text, className = '' }) {
  if (!text) return null;
  const parts = text.split(/(\[\[[^\]]+\]\])/g);
  return (
    <p className={`text-xs text-muted-foreground leading-relaxed ${className}`}>
      {parts.map((part, i) =>
        part.startsWith('[[') && part.endsWith(']]') ? (
          <mark
            key={i}
            className="bg-primary/10 text-primary rounded px-1 py-0.5 font-mono text-[11px]"
          >
            {part.slice(2, -2)}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </p>
  );
}
