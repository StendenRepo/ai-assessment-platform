'use client';

import { Upload } from 'lucide-react';

export default function EvidenceUploadPanel({
  title = 'Upload Evidence',
  acceptedLabel,
  uploading = false,
  uploadingCount = 0,
  uploadingFileName = '',
  dragOver = false,
  fileInputRef,
  accept,
  onInputChange,
  onDragOver,
  onDragLeave,
  onDrop,
  onOpenFilePicker,
}) {
  const uploadStatusText = uploading
    ? `Uploading ${uploadingCount} file${uploadingCount === 1 ? '' : 's'}...`
    : 'Drop file(s) here or click to browse';

  const uploadDetailText = uploading
    ? 'You can continue adding more files while AI image processing runs in the background.'
    : `Accepted: ${acceptedLabel}`;

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-secondary/30">
        <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center">
          <Upload size={13} className="text-primary" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="text-[11px] text-muted-foreground">
            Accepted: <code className="font-mono">{acceptedLabel}</code>
          </p>
        </div>
      </div>

      <div className="p-5">
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={onOpenFilePicker}
          className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors ${
            dragOver
              ? 'border-primary bg-primary/5'
              : 'border-border hover:border-primary/50 hover:bg-secondary/50'
          }`}
        >
          <Upload
            size={22}
            className={dragOver ? 'text-primary' : 'text-muted-foreground'}
          />
          <p className="text-sm font-medium text-foreground">
            {uploadStatusText}
          </p>
          <p className="text-xs text-muted-foreground">{uploadDetailText}</p>
          {uploadingFileName && (
            <p className="text-[11px] font-mono text-muted-foreground text-center break-all">
              Latest: {uploadingFileName}
            </p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept={accept}
            multiple
            className="hidden"
            onChange={onInputChange}
          />
        </div>
      </div>
    </div>
  );
}
