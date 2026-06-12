'use client';

import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog';
import EvidenceListItem from '@/components/evidence/EvidenceListItem';
import EvidencePreviewDialog from '@/components/evidence/EvidencePreviewDialog';
import EvidenceUploadPanel from '@/components/evidence/EvidenceUploadPanel';
import { useDeleteConfirm } from '@/lib/hooks/useDeleteConfirm';
import { useEvidencePreview } from '@/components/evidence/useEvidencePreview';
import { deleteEvidence, getSupportedEvidenceTypes } from '@/lib/api/evidence';
import {
  listProjectEvidence,
  uploadProjectEvidence,
} from '@/lib/api/modulesApi';

const DEFAULT_EVIDENCE_EXTENSIONS = [
  '.md',
  '.docx',
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
];

export default function ProjectEvidencePanel({
  projectId,
  title = 'Shared Evidence',
}) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [allEvidence, setAllEvidence] = useState([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState('');
  const [error, setError] = useState('');
  const [allowedExtensions, setAllowedExtensions] = useState(
    DEFAULT_EVIDENCE_EXTENSIONS
  );

  const {
    previewEvidence,
    previewUrl,
    previewContent,
    previewLoading,
    activePreviewKind,
    basePreviewKind,
    showImageExtractedText,
    canPreview,
    openPreview,
    closePreview,
    toggleImageExtractedText,
    downloadEvidence,
  } = useEvidencePreview();

  const { pendingItem, requestDelete, cancelDelete, confirmDelete } =
    useDeleteConfirm({
      onDelete: (item) => deleteEvidence(item.id),
      onDeleted: (deletedEvidence) => {
        setAllEvidence((prev) =>
          prev.filter((ev) => ev.id !== deletedEvidence.id)
        );
      },
      onError: (err) => {
        setError(err.message);
      },
    });

  useEffect(() => {
    let active = true;
    getSupportedEvidenceTypes()
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data.supported_extensions)) {
          setAllowedExtensions(data.supported_extensions);
        }
      })
      .catch(() => {
        // Keep the default list if the request fails.
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!projectId) return;

    const loadEvidence = async () => {
      setEvidenceLoading(true);
      try {
        const data = await listProjectEvidence(projectId).catch(() => []);
        setAllEvidence(Array.isArray(data) ? data : []);
      } catch {
        setAllEvidence([]);
      } finally {
        setEvidenceLoading(false);
      }
    };

    loadEvidence();
  }, [projectId]);

  useEffect(() => {
    if (!projectId) return;

    const hasProcessing = allEvidence.some(
      (evidence) => evidence.embedding_status === 'processing'
    );
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const fresh = await listProjectEvidence(projectId);
        if (!Array.isArray(fresh)) return;
        setAllEvidence((prev) => {
          let changed = false;
          const next = prev.map((ev) => {
            const updated = fresh.find((item) => item.id === ev.id);
            if (updated && updated.embedding_status !== ev.embedding_status) {
              changed = true;
              if (updated.embedding_status === 'completed') {
                setUploadSuccessMessage(
                  `Upload complete: ${updated.file_name}`
                );
                window.setTimeout(() => setUploadSuccessMessage(''), 4000);
              }
              return updated;
            }
            return ev;
          });
          return changed ? next : prev;
        });
      } catch {
        // Ignore polling errors; the panel remains usable.
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [allEvidence, projectId]);

  const isAllowed = (filename) => {
    const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
    return allowedExtensions.includes(ext);
  };

  const handleSingleFile = async (file) => {
    setError('');
    if (!isAllowed(file.name)) {
      setError(
        `Unsupported file type. Allowed: ${allowedExtensions.join(', ')}`
      );
      return;
    }

    setUploading(true);
    try {
      const uploaded = await uploadProjectEvidence(projectId, file);
      setAllEvidence([uploaded]);
      if (uploaded.embedding_status === 'completed') {
        setUploadSuccessMessage(`Upload complete: ${uploaded.file_name}`);
        window.setTimeout(() => setUploadSuccessMessage(''), 4000);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const onInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      void handleSingleFile(file);
    }
    e.target.value = '';
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      void handleSingleFile(file);
    }
  };

  const handleDelete = (evidenceId) => {
    const evidence = allEvidence.find((item) => item.id === evidenceId);
    if (evidence) {
      requestDelete(evidence);
    }
  };

  const handlePreview = async (evidence) => {
    setError('');
    try {
      await openPreview(evidence);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDownload = async (evidence) => {
    setError('');
    try {
      await downloadEvidence(evidence);
    } catch (err) {
      setError(err.message);
    }
  };

  if (!projectId) {
    return null;
  }

  return (
    <div className="space-y-4">
      <EvidenceUploadPanel
        title={title}
        acceptedLabel={allowedExtensions.join(', ')}
        uploading={uploading}
        uploadingCount={uploading ? 1 : 0}
        uploadingFileName={uploading ? 'Uploading shared evidence…' : ''}
        dragOver={dragOver}
        fileInputRef={fileInputRef}
        accept={allowedExtensions.join(',')}
        onInputChange={onInputChange}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onOpenFilePicker={() => fileInputRef.current?.click()}
      />

      {uploadSuccessMessage && (
        <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
          <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
          <p className="text-xs text-emerald-400">{uploadSuccessMessage}</p>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2">
          <XCircle size={13} className="text-red-400 shrink-0" />
          <p className="text-xs text-red-400">{error}</p>
        </div>
      )}

      <div className="rounded-lg border border-border overflow-hidden">
        <div className="p-5 space-y-2">
          <p className="text-xs font-semibold text-foreground uppercase tracking-wide">
            Evidence ({allEvidence.length})
          </p>
          {evidenceLoading ? (
            <div className="flex justify-center py-4">
              <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : allEvidence.length === 0 ? (
            <p className="text-xs text-muted-foreground py-2">
              No shared evidence uploaded yet.
            </p>
          ) : (
            allEvidence.map((evidence) => (
              <EvidenceListItem
                key={evidence.id}
                evidence={evidence}
                canPreview={!evidence.__localProcessing && canPreview(evidence)}
                onPreview={handlePreview}
                onDownload={handleDownload}
                onDelete={handleDelete}
              />
            ))
          )}
        </div>
      </div>

      <EvidencePreviewDialog
        evidence={previewEvidence}
        previewKind={activePreviewKind}
        basePreviewKind={basePreviewKind}
        previewUrl={previewUrl}
        previewContent={previewContent}
        loading={previewLoading}
        showImageExtractedText={showImageExtractedText}
        onToggleImageExtractedText={toggleImageExtractedText}
        onClose={closePreview}
      />

      <DeleteConfirmDialog
        open={Boolean(pendingItem)}
        label={pendingItem?.file_name}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      />
    </div>
  );
}
