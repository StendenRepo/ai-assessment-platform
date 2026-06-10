'use client';

import { useEffect, useState } from 'react';

import { getEvidenceContent, getEvidenceFileBlob } from '@/lib/api/evidence';

export function getEvidencePreviewKind(evidence) {
  if (!evidence) return null;
  if (evidence.file_type === 'image') return 'image';
  if (evidence.file_type === 'pdf') return 'pdf';
  if (evidence.file_type === 'markdown' || evidence.file_type === 'docx') {
    return 'text';
  }
  return null;
}

export function useEvidencePreview() {
  const [previewEvidence, setPreviewEvidence] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewContent, setPreviewContent] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const releasePreviewUrl = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  };

  const resetPreviewState = () => {
    releasePreviewUrl();
    setPreviewContent('');
  };

  const openPreview = async (evidence) => {
    const kind = getEvidencePreviewKind(evidence);
    if (!kind) return;

    setPreviewEvidence(evidence);
    setPreviewLoading(true);
    try {
      resetPreviewState();

      if (kind === 'image' || kind === 'pdf') {
        const blob = await getEvidenceFileBlob(evidence.id);
        setPreviewUrl(URL.createObjectURL(blob));
      } else {
        const content = await getEvidenceContent(evidence.id);
        setPreviewContent(content);
      }
    } catch (error) {
      setPreviewEvidence(null);
      throw error;
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    resetPreviewState();
    setPreviewEvidence(null);
    setPreviewLoading(false);
  };

  const downloadEvidence = async (evidence) => {
    const blob = await getEvidenceFileBlob(evidence.id);
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = evidence.file_name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(blobUrl);
  };

  return {
    previewEvidence,
    previewUrl,
    previewContent,
    previewLoading,
    activePreviewKind: getEvidencePreviewKind(previewEvidence),
    canPreview: (evidence) => getEvidencePreviewKind(evidence) !== null,
    openPreview,
    closePreview,
    downloadEvidence,
  };
}
