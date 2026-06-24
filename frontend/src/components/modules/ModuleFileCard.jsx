'use client';

import { Download, Eye, RefreshCw, Trash2, Upload } from 'lucide-react';
import EvidenceStatusIndicator from '@/components/evidence/EvidenceStatusIndicator';
import { getPreviewKind } from '@/lib/hooks/useDocumentPreview';

function formatBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export default function ModuleFileCard({
  title,
  icon: Icon,
  description,
  accept,
  file,
  fallbackName,
  descriptor,
  inputRef,
  uploading,
  deleting,
  error,
  onFileChange,
  onDelete,
  docPreview,
  readOnly = false,
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
        <Icon size={16} />
        {title}
      </h3>
      <div
        className={`rounded-lg bg-card border border-border px-5 pt-5 space-y-4 ${file ? 'pb-3' : 'pb-5'}`}
      >
        <p className="text-xs text-muted-foreground">{description}</p>

        {file ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-lg bg-secondary border border-border px-3 py-3">
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Icon size={16} className="text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground truncate">
                    {file.file_name || fallbackName}
                  </span>
                  <EvidenceStatusIndicator status="completed" size={13} />
                </div>
                <div className="text-xs text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  {file.file_type && (
                    <span className="uppercase font-mono">
                      {file.file_type}
                    </span>
                  )}
                  {file.size_bytes && (
                    <span>{formatBytes(file.size_bytes)}</span>
                  )}
                  {file.uploaded_at && (
                    <span>Uploaded {formatDate(file.uploaded_at)}</span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex gap-2">
              {getPreviewKind(file.file_type) && (
                <button
                  type="button"
                  onClick={() => docPreview.openPreview(descriptor)}
                  title="View"
                  className="flex-1 flex items-center justify-center p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
                >
                  <Eye size={14} />
                </button>
              )}
              <button
                type="button"
                onClick={() => docPreview.download(descriptor)}
                title="Download"
                className="flex-1 flex items-center justify-center p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                <Download size={14} />
              </button>
              {!readOnly && (
                <>
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    disabled={uploading}
                    title="Replace"
                    className="flex-1 flex items-center justify-center p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-50"
                  >
                    <RefreshCw size={14} />
                  </button>
                  <button
                    type="button"
                    onClick={onDelete}
                    disabled={deleting}
                    title="Remove"
                    className="flex-1 flex items-center justify-center p-2 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50"
                  >
                    <Trash2 size={14} />
                  </button>
                </>
              )}
            </div>

            {!readOnly && (
              <input
                ref={inputRef}
                type="file"
                accept={accept}
                onChange={(e) => onFileChange(e.target.files?.[0])}
                className="hidden"
              />
            )}
          </div>
        ) : !readOnly ? (
          <div>
            <input
              ref={inputRef}
              type="file"
              accept={accept}
              onChange={(e) => onFileChange(e.target.files?.[0])}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md border border-border bg-secondary text-sm font-semibold text-foreground hover:bg-secondary/70 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Upload size={15} />
              {uploading ? 'Uploading…' : 'Choose file'}
            </button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic">
            No file attached.
          </p>
        )}

        {error && (
          <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
