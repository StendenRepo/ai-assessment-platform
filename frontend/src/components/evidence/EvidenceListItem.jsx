'use client';

import {
  Download,
  Eye,
  FileText,
  Image as ImageIcon,
  Loader2,
  Trash2,
} from 'lucide-react';

import EvidenceStatusIndicator from '@/components/evidence/EvidenceStatusIndicator';

function renderEvidenceIcon(fileType) {
  if (fileType === 'image') {
    return <ImageIcon size={14} className="text-primary shrink-0" />;
  }

  return <FileText size={14} className="text-primary shrink-0" />;
}

export default function EvidenceListItem({
  evidence,
  canPreview,
  onPreview,
  onDownload,
  onDelete,
}) {
  const isLocalProcessing = Boolean(evidence.__localProcessing);
  const scopeLabel = evidence.project_id ? 'Project-level' : 'Individual';
  // Server-side background AI processing (image uploaded, vision not yet done)
  const isServerProcessing =
    !isLocalProcessing && evidence.embedding_status === 'processing';

  const statusLabel =
    evidence.__statusLabel ||
    (evidence.embedding_status === 'completed'
      ? 'Completed'
      : evidence.embedding_status === 'failed'
        ? 'Failed'
        : isServerProcessing
          ? 'Processing image with AI'
          : 'Processing');

  const statusBadgeClass =
    isLocalProcessing || isServerProcessing
      ? 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20'
      : evidence.embedding_status === 'completed'
        ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20'
        : evidence.embedding_status === 'failed'
          ? 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20'
          : 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20';

  return (
    <div className="flex items-center gap-3 rounded-md bg-card border border-border px-3 py-2.5">
      {renderEvidenceIcon(evidence.file_type)}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-foreground font-mono truncate">
          {evidence.file_name}
        </p>
        <p className="text-[10px] text-muted-foreground">
          {new Date(evidence.uploaded_at).toLocaleString('nl-NL')}
          {' · '}
          <span className="uppercase font-semibold tracking-wide">
            {scopeLabel}
          </span>
          {' · '}
          <span className="capitalize">{evidence.file_type}</span>
          {' · '}
          <EvidenceStatusIndicator status={evidence.embedding_status} />{' '}
          <span
            className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${statusBadgeClass}`}
          >
            {isServerProcessing && (
              <Loader2 size={9} className="animate-spin shrink-0" />
            )}
            {statusLabel}
          </span>
        </p>
      </div>
      {canPreview && !isLocalProcessing && !isServerProcessing && (
        <button
          onClick={() => onPreview(evidence)}
          title="Preview evidence"
          className="shrink-0 p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        >
          <Eye size={13} />
        </button>
      )}
      {!isLocalProcessing && (
        <>
          <button
            onClick={() => onDownload(evidence)}
            title="Download evidence"
            className="shrink-0 p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          >
            <Download size={13} />
          </button>
          <button
            onClick={() => onDelete(evidence.id)}
            title="Delete evidence"
            className="shrink-0 p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-colors"
          >
            <Trash2 size={13} />
          </button>
        </>
      )}
    </div>
  );
}
