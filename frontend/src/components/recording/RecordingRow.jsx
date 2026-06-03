'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  MoreVertical,
  Pencil,
  CalendarClock,
  Trash2,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Check,
  X,
} from 'lucide-react';
import {
  getRecording,
  renameRecording,
  extendRecordingExpiry,
  deleteRecording,
} from '@/lib/recording';
import ExtendExpiryDialog from '@/components/recording/ExtendExpiryDialog';

const statusConfig = {
  pending: { label: 'Queued', cls: 'text-amber-400', spin: true },
  processing: { label: 'Transcribing…', cls: 'text-amber-400', spin: true },
  completed: { label: 'Transcribed', cls: 'text-emerald-400', spin: false },
  failed: { label: 'Transcription failed', cls: 'text-red-400', spin: false },
};

export default function RecordingRow({
  assessmentId,
  recording,
  onChanged,
  onError,
}) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState(recording.display_name);
  const [showExtend, setShowExtend] = useState(false);
  const [busy, setBusy] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function onClick(e) {
      if (menuRef.current && !menuRef.current.contains(e.target))
        setMenuOpen(false);
    }
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const status =
    statusConfig[recording.transcription_status] ?? statusConfig.pending;

  async function toggleExpand() {
    const next = !expanded;
    setExpanded(next);
    if (next && !detail) {
      try {
        setDetail(await getRecording(assessmentId, recording.id));
      } catch (e) {
        onError?.(e.message);
      }
    }
  }

  async function saveRename() {
    if (!nameDraft.trim()) return;
    setBusy(true);
    try {
      await renameRecording(assessmentId, recording.id, nameDraft.trim());
      setRenaming(false);
      onChanged?.();
    } catch (e) {
      onError?.(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (
      !window.confirm(
        `Delete “${recording.display_name}”? The audio file will be removed.`
      )
    )
      return;
    setBusy(true);
    try {
      await deleteRecording(assessmentId, recording.id);
      onChanged?.();
    } catch (e) {
      onError?.(e.message);
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-border">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <button
          onClick={toggleExpand}
          className="flex items-center gap-2 flex-1 min-w-0 text-left"
        >
          {expanded ? (
            <ChevronDown size={15} className="text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight
              size={15}
              className="text-muted-foreground shrink-0"
            />
          )}
          {renaming ? (
            <input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              className="flex-1 bg-secondary border border-border rounded px-2 py-1 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
          ) : (
            <span className="text-sm font-medium text-foreground truncate">
              {recording.display_name}
            </span>
          )}
        </button>

        {renaming ? (
          <>
            <button
              onClick={saveRename}
              disabled={busy}
              className="p-1 text-emerald-400 hover:bg-secondary rounded"
            >
              <Check size={15} />
            </button>
            <button
              onClick={() => {
                setRenaming(false);
                setNameDraft(recording.display_name);
              }}
              className="p-1 text-muted-foreground hover:bg-secondary rounded"
            >
              <X size={15} />
            </button>
          </>
        ) : (
          <>
            <span
              className={`flex items-center gap-1 text-[11px] ${status.cls} shrink-0`}
            >
              {status.spin ? (
                <Loader2 size={12} className="animate-spin" />
              ) : recording.transcription_status === 'completed' ? (
                <CheckCircle2 size={12} />
              ) : (
                <AlertTriangle size={12} />
              )}
              {status.label}
            </span>

            {recording.flagged_for_deletion ? (
              <span className="text-[10px] text-red-400 shrink-0">flagged</span>
            ) : (
              recording.delete_after && (
                <span className="text-[10px] text-muted-foreground shrink-0">
                  exp {new Date(recording.delete_after).toLocaleDateString()}
                </span>
              )
            )}

            <div className="relative shrink-0" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((o) => !o)}
                disabled={busy}
                className="p-1 text-muted-foreground hover:bg-secondary rounded disabled:opacity-50"
                aria-label="Recording actions"
              >
                {busy ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <MoreVertical size={15} />
                )}
              </button>
              {menuOpen && (
                <div className="absolute right-0 mt-1 w-40 rounded-md bg-card border border-border shadow-xl z-20 overflow-hidden">
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      setRenaming(true);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-foreground hover:bg-secondary text-left"
                  >
                    <Pencil size={13} /> Rename
                  </button>
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      setShowExtend(true);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-foreground hover:bg-secondary text-left"
                  >
                    <CalendarClock size={13} /> Extend expiry
                  </button>
                  <button
                    onClick={() => {
                      setMenuOpen(false);
                      handleDelete();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-secondary text-left"
                  >
                    <Trash2 size={13} /> Delete
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {expanded && (
        <div className="border-t border-border bg-secondary/30 px-4 py-3 rounded-b-lg">
          {detail ? (
            detail.transcription_status === 'completed' ? (
              <div className="text-xs text-muted-foreground whitespace-pre-wrap max-h-48 overflow-y-auto">
                {detail.transcript_text || '(empty transcript)'}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                {detail.transcription_status === 'failed'
                  ? 'Transcription failed for this recording.'
                  : 'Transcription in progress…'}
              </p>
            )
          ) : (
            <p className="text-xs text-muted-foreground flex items-center gap-2">
              <Loader2 size={12} className="animate-spin" /> Loading…
            </p>
          )}
        </div>
      )}

      {showExtend && (
        <ExtendExpiryDialog
          recording={recording}
          onClose={() => setShowExtend(false)}
          onSubmit={async ({ reason, extraDays }) => {
            await extendRecordingExpiry(assessmentId, recording.id, {
              reason,
              extraDays,
            });
            onChanged?.();
          }}
        />
      )}
    </div>
  );
}
