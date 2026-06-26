'use client';

import { getEvidenceContent, getEvidenceFileBlob } from '@/lib/api/evidence';
import {
  getPreviewKind,
  useDocumentPreview,
} from '@/lib/hooks/useDocumentPreview';

export function getEvidencePreviewKind(evidence) {
  if (!evidence) return null;
  return getPreviewKind(evidence.file_type);
}

function toDescriptor(evidence) {
  return {
    file_name: evidence.file_name,
    file_type: evidence.file_type,
    fetchBlob: () => getEvidenceFileBlob(evidence.id),
    fetchContent: () => getEvidenceContent(evidence.id),
    supportsAltText: evidence.file_type === 'image',
  };
}

export function useEvidencePreview() {
  const preview = useDocumentPreview();

  return {
    previewEvidence: preview.previewDoc,
    previewUrl: preview.previewUrl,
    previewContent: preview.previewContent,
    previewLoading: preview.previewLoading,
    activePreviewKind: preview.activePreviewKind,
    basePreviewKind: preview.basePreviewKind,
    showImageExtractedText: preview.showImageExtractedText,
    canPreview: (evidence) => getEvidencePreviewKind(evidence) !== null,
    openPreview: (evidence) => preview.openPreview(toDescriptor(evidence)),
    closePreview: preview.closePreview,
    toggleImageExtractedText: preview.toggleImageExtractedText,
    downloadEvidence: (evidence) => preview.download(toDescriptor(evidence)),
  };
}
