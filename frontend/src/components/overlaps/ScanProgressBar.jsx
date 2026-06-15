'use client';

import { useEffect, useRef, useState } from 'react';

const STAGES = [
  'Checking submissions for AI-generated content…',
  'Comparing student work for similarities…',
  'Finishing review…',
];

export default function ScanProgressBar({ active }) {
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState(0);
  const [visible, setVisible] = useState(false);
  const wasActive = useRef(false);

  useEffect(() => {
    if (active) {
      wasActive.current = true;
      setVisible(true);
      setProgress(8);
      setStage(0);

      const tick = setInterval(() => {
        setProgress((current) => {
          if (current >= 94) return current;
          const step = current < 35 ? 2.5 : current < 65 ? 1.2 : 0.4;
          return Math.min(94, current + step);
        });
      }, 600);

      const advanceStage = setInterval(() => {
        setStage((current) => Math.min(STAGES.length - 1, current + 1));
      }, 14000);

      return () => {
        clearInterval(tick);
        clearInterval(advanceStage);
      };
    }

    if (!wasActive.current) return undefined;

    setProgress(100);
    const hide = setTimeout(() => {
      setVisible(false);
      setProgress(0);
      setStage(0);
      wasActive.current = false;
    }, 500);

    return () => clearTimeout(hide);
  }, [active]);

  if (!visible) return null;

  return (
    <div
      className="rounded-lg border border-border bg-card px-4 py-3 space-y-2"
      role="status"
      aria-live="polite"
      aria-busy={active}
    >
      <div className="flex items-center justify-between gap-3 text-sm">
        <span className="text-foreground font-medium">Scanning module</span>
        <span className="font-mono tabular-nums text-muted-foreground text-xs">
          {Math.round(progress)}%
        </span>
      </div>
      <div className="h-2 rounded-full bg-secondary overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{STAGES[stage]}</p>
    </div>
  );
}
