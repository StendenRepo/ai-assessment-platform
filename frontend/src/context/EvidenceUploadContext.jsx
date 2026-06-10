'use client';

import { createContext, useContext, useRef, useState } from 'react';

import { uploadStudentEvidence } from '@/lib/api/evidence';

const EvidenceUploadContext = createContext(null);

function _fileTypeFromName(filename) {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  if (['.png', '.jpg', '.jpeg'].includes(ext)) return 'image';
  if (ext === '.pdf') return 'pdf';
  if (ext === '.docx') return 'docx';
  if (ext === '.md') return 'markdown';
  return 'unknown';
}

export function EvidenceUploadProvider({ children }) {
  // Map<studentId, Map<localId, localEntry>>
  const [inFlightMap, setInFlightMap] = useState(() => new Map());
  // Map<studentId, Evidence[]> — items that completed while the page wasn't mounted
  const completedWhileAwayRef = useRef(new Map());
  // Map<studentId, {onCompleted, onError}> — live callbacks registered by the mounted page
  const liveCallbacksRef = useRef(new Map());
  const ocrTimeoutsRef = useRef(new Map());

  /** Called by the mounted page to register live callbacks. Returns a cleanup fn. */
  const registerCallbacks = (studentId, callbacks) => {
    liveCallbacksRef.current.set(studentId, callbacks);
    return () => liveCallbacksRef.current.delete(studentId);
  };

  const _addItem = (studentId, entry) =>
    setInFlightMap((prev) => {
      const next = new Map(prev);
      const m = new Map(next.get(studentId) ?? []);
      m.set(entry.id, entry);
      next.set(studentId, m);
      return next;
    });

  const _updateItem = (studentId, localId, updates) =>
    setInFlightMap((prev) => {
      const next = new Map(prev);
      const m = new Map(next.get(studentId) ?? []);
      const existing = m.get(localId);
      if (!existing) return prev;
      m.set(localId, { ...existing, ...updates });
      next.set(studentId, m);
      return next;
    });

  const _removeItem = (studentId, localId) =>
    setInFlightMap((prev) => {
      const next = new Map(prev);
      const m = new Map(next.get(studentId) ?? []);
      m.delete(localId);
      next.set(studentId, m);
      return next;
    });

  /**
   * Start uploading a single file for a student.
   * Callbacks fire whether or not the component that triggered this is still mounted.
   */
  const startUpload = (studentId, file) => {
    const isImage = /\.(png|jpe?g)$/i.test(file.name);
    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    _addItem(studentId, {
      id: localId,
      file_name: file.name,
      file_type: _fileTypeFromName(file.name),
      uploaded_at: new Date().toISOString(),
      embedding_status: 'pending',
      __localProcessing: true,
      __statusLabel: 'Uploading',
    });

    if (isImage) {
      const tid = window.setTimeout(() => {
        _updateItem(studentId, localId, {
          __statusLabel: 'Processing image with AI',
        });
      }, 1800);
      ocrTimeoutsRef.current.set(localId, tid);
    }

    uploadStudentEvidence(studentId, file)
      .then((data) => {
        _removeItem(studentId, localId);
        const live = liveCallbacksRef.current.get(studentId);
        if (live?.onCompleted) {
          live.onCompleted(data);
        } else {
          // Page was not mounted — stash for when it mounts next
          const stash = completedWhileAwayRef.current;
          const list = stash.get(studentId) ?? [];
          stash.set(studentId, [...list, data]);
        }
      })
      .catch((err) => {
        _removeItem(studentId, localId);
        const live = liveCallbacksRef.current.get(studentId);
        live?.onError?.(err);
      })
      .finally(() => {
        const tid = ocrTimeoutsRef.current.get(localId);
        if (tid) {
          window.clearTimeout(tid);
          ocrTimeoutsRef.current.delete(localId);
        }
      });
  };

  /** Returns the live in-flight local items for a specific student. */
  const getStudentLocalItems = (studentId) =>
    Array.from(inFlightMap.get(studentId)?.values() ?? []);

  /**
   * Returns any items that completed while the student page was not mounted,
   * and clears them so they are only consumed once.
   */
  const consumeCompletedItems = (studentId) => {
    const stash = completedWhileAwayRef.current;
    const items = stash.get(studentId) ?? [];
    stash.delete(studentId);
    return items;
  };

  return (
    <EvidenceUploadContext.Provider
      value={{
        startUpload,
        registerCallbacks,
        getStudentLocalItems,
        consumeCompletedItems,
        inFlightMap,
      }}
    >
      {children}
    </EvidenceUploadContext.Provider>
  );
}

export function useEvidenceUpload() {
  const ctx = useContext(EvidenceUploadContext);
  if (!ctx) {
    throw new Error(
      'useEvidenceUpload must be used inside EvidenceUploadProvider'
    );
  }
  return ctx;
}
