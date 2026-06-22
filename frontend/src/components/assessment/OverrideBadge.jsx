'use client';

import { MessageSquare, PenLine, Sparkles } from 'lucide-react';

export default function OverrideBadge({ isOverridden, refinedViaChat }) {
  if (isOverridden) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20">
        <PenLine size={10} />
        Teacher override
      </span>
    );
  }
  if (refinedViaChat) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-violet-500/10 text-violet-400 ring-1 ring-violet-500/20">
        <MessageSquare size={10} />
        Refined via chat
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20">
      <Sparkles size={10} />
      AI suggestion
    </span>
  );
}
