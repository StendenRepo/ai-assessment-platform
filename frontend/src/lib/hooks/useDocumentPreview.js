'use client';

import { useEffect, useState } from 'react';

/**
 * Map a stored file type to how it should be rendered inline.
 *
 * Accepts both the evidence `FileType` enum values ('image', 'pdf',
 * 'markdown', 'docx') and the raw extensions stored on module documents
 * ('pdf', 'docx', 'xlsx', ...). Anything we can't render inline (e.g. xlsx
 * rubrics) returns null so callers fall back to download-only.
 */
export function getPreviewKind(fileType) {
  const type = (fileType || '').toLowerCase();
  if (['image', 'png', 'jpg', 'jpeg'].includes(type)) return 'image';
  if (type === 'pdf') return 'pdf';
  if (['markdown', 'md', 'docx'].includes(type)) return 'text';
  return null;
}

/**
 * Source-agnostic document preview state machine, shared by the evidence and
 * module-document viewers. Callers drive it with a descriptor:
 *
 *   {
 *     file_name,        // shown in the dialog header
 *     file_type,        // drives getPreviewKind
 *     fetchBlob,        // () => Promise<Blob>  (image/pdf)
 *     fetchContent,     // () => Promise<string> (text, and image alt-text)
 *     supportsAltText,  // images: allow toggling to extracted text
 *   }
 */
export function useDocumentPreview() {
  const [previewDoc, setPreviewDoc] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewContent, setPreviewContent] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showImageExtractedText, setShowImageExtractedText] = useState(false);

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
    setShowImageExtractedText(false);
  };

  const openPreview = async (doc) => {
    const kind = getPreviewKind(doc?.file_type);
    if (!kind) return;

    setPreviewDoc(doc);
    setPreviewLoading(true);
    try {
      resetPreviewState();

      if (kind === 'image' || kind === 'pdf') {
        const blob = await doc.fetchBlob();
        setPreviewUrl(URL.createObjectURL(blob));
      } else {
        const content = await doc.fetchContent();
        setPreviewContent(content);
      }
    } catch (error) {
      setPreviewDoc(null);
      throw error;
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    resetPreviewState();
    setPreviewDoc(null);
    setPreviewLoading(false);
  };

  const toggleImageExtractedText = async () => {
    if (!previewDoc?.supportsAltText) return;

    if (showImageExtractedText) {
      setShowImageExtractedText(false);
      return;
    }

    if (previewContent) {
      setShowImageExtractedText(true);
      return;
    }

    setPreviewLoading(true);
    try {
      const content = await previewDoc.fetchContent();
      setPreviewContent(content);
      setShowImageExtractedText(true);
    } finally {
      setPreviewLoading(false);
    }
  };

  const basePreviewKind = getPreviewKind(previewDoc?.file_type);
  const activePreviewKind =
    basePreviewKind === 'image' && showImageExtractedText
      ? 'text'
      : basePreviewKind;

  const download = async (doc) => {
    const blob = await doc.fetchBlob();
    const blobUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = doc.file_name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(blobUrl);
  };

  return {
    previewDoc,
    previewUrl,
    previewContent,
    previewLoading,
    activePreviewKind,
    basePreviewKind,
    showImageExtractedText,
    canPreview: (fileType) => getPreviewKind(fileType) !== null,
    openPreview,
    closePreview,
    toggleImageExtractedText,
    download,
  };
}
