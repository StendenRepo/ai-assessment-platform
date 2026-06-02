'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import { Upload, FileText, Trash2, RefreshCw, CheckCircle2 } from 'lucide-react';
import { getModule, uploadRubric, deleteRubric } from '@/lib/modulesApi';

const ALLOWED_TYPES = '.pdf,.xlsx';
const ALLOWED_LABEL = 'PDF or Excel (.xlsx)';

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

export default function ModulePage() {
  const { moduleId } = useParams();
  const fileInputRef = useRef(null);

  const [module, setModule] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  useEffect(() => {
    getModule(moduleId)
      .then(setModule)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [moduleId]);

  const handleFile = async (file) => {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'xlsx') {
      setUploadError(`Only PDF and Excel files are allowed. "${file.name}" is not supported.`);
      return;
    }

    setUploadError(null);
    setUploading(true);
    try {
      const updated = await uploadRubric(moduleId, file);
      setModule(updated);
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDelete = async () => {
    if (!confirm('Remove the rubric from this module?')) return;
    setDeleting(true);
    try {
      const updated = await deleteRubric(moduleId);
      setModule((prev) => ({ ...prev, rubric_file: null }));
    } catch (e) {
      setUploadError(e.message);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
        {error}
      </div>
    );
  }

  const rubric = module?.rubric_file;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{module?.name}</h1>
        {module?.academic_year && (
          <p className="text-sm text-muted-foreground mt-1">{module.academic_year}</p>
        )}
      </div>

      <div className="rounded-lg bg-card border border-border p-6 space-y-5">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Rubric File</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Attach a rubric so the AI knows the grading criteria for this module.
            Only {ALLOWED_LABEL} files are accepted.
          </p>
        </div>

        {rubric ? (
          <div className="space-y-4">
            <div className="flex items-center gap-4 rounded-lg bg-secondary border border-border px-4 py-3">
              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <FileText size={16} className="text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-foreground truncate">
                    {rubric.file_name || 'rubric'}
                  </span>
                  <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
                </div>
                <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                  {rubric.file_type && (
                    <span className="uppercase font-mono">{rubric.file_type}</span>
                  )}
                  {rubric.size_bytes && <span>{formatBytes(rubric.size_bytes)}</span>}
                  {rubric.uploaded_at && <span>Uploaded {formatDate(rubric.uploaded_at)}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card transition-all disabled:opacity-50"
                >
                  <RefreshCw size={12} /> Replace
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-destructive/30 text-xs font-medium text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50"
                >
                  <Trash2 size={12} /> {deleting ? 'Removing...' : 'Remove'}
                </button>
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_TYPES}
              onChange={(e) => handleFile(e.target.files?.[0])}
              className="hidden"
            />
          </div>
        ) : (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-10 text-center transition-all ${
              dragActive
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/40'
            }`}
          >
            <Upload size={28} className="mx-auto text-muted-foreground mb-3" />
            <p className="text-sm font-medium text-foreground mb-1">
              {uploading ? 'Uploading...' : 'Drop your rubric here'}
            </p>
            <p className="text-xs text-muted-foreground mb-4">{ALLOWED_LABEL} only</p>
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_TYPES}
              onChange={(e) => handleFile(e.target.files?.[0])}
              className="hidden"
              id="rubric-upload"
            />
            <label
              htmlFor="rubric-upload"
              className={`inline-block px-4 py-2 rounded-md border border-border text-sm font-medium text-foreground cursor-pointer hover:bg-secondary transition-all ${
                uploading ? 'opacity-50 pointer-events-none' : ''
              }`}
            >
              Browse files
            </label>
          </div>
        )}

        {uploadError && (
          <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
            {uploadError}
          </div>
        )}
      </div>
    </div>
  );
}
