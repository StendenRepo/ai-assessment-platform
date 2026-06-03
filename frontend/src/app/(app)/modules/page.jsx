'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  ArrowRight,
  SlidersHorizontal,
  Users,
  FileText,
  Pencil,
  Trash2,
  Check,
  X,
  AlertTriangle,
} from 'lucide-react';
import { listModules, renameModule, deleteModule } from '@/lib/modulesApi';
import { APP_PATHS } from '@/lib/routes';

const statusConfig = {
  active: {
    label: 'Active',
    classes: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
  },
  completed: {
    label: 'Completed',
    classes: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
  },
  archived: {
    label: 'Archived',
    classes: 'bg-secondary text-muted-foreground ring-1 ring-border',
  },
};

// ---------------------------------------------------------------------------
// Confirmation modal
// ---------------------------------------------------------------------------

function DeleteConfirmModal({ module, onConfirm, onCancel, loading }) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onCancel]);

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onCancel}
    >
      {/* Panel */}
      <div
        className="relative w-full max-w-md mx-4 rounded-xl bg-card border border-border shadow-2xl p-6 space-y-5"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
            <AlertTriangle size={18} className="text-red-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Delete module</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Are you sure you want to delete{' '}
              <span className="font-medium text-foreground">{module.name}</span>?
            </p>
          </div>
        </div>

        {/* Warning */}
        <div className="rounded-lg bg-red-500/5 border border-red-500/20 px-4 py-3 text-xs text-red-400 space-y-1">
          <p className="font-medium">This action cannot be undone. It will permanently delete:</p>
          <ul className="list-disc list-inside space-y-0.5 text-red-400/80">
            <li>The module and all its settings</li>
            <li>All groups and students in this module</li>
            <li>All uploaded evidence files</li>
            <li>The rubric file (if any)</li>
          </ul>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-1">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-muted-foreground bg-secondary hover:bg-secondary/80 border border-border transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-red-600 hover:bg-red-700 transition-colors disabled:opacity-60 flex items-center gap-2"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Trash2 size={14} />
            )}
            Delete module
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ModulesPage() {
  const router = useRouter();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  // Rename state
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameLoading, setRenameLoading] = useState(false);
  const renameInputRef = useRef(null);

  // Delete modal state
  const [deleteTarget, setDeleteTarget] = useState(null); // { id, name }
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await listModules();
        setProjects(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Focus rename input when it appears
  useEffect(() => {
    if (renamingId) renameInputRef.current?.focus();
  }, [renamingId]);

  const filtered = projects.filter((p) => {
    const matchSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = statusFilter === 'all' || p.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const startRename = (e, module) => {
    e.stopPropagation();
    setRenamingId(module.id);
    setRenameValue(module.name);
  };

  const cancelRename = (e) => {
    e?.stopPropagation();
    setRenamingId(null);
    setRenameValue('');
  };

  const confirmRename = async (e, moduleId) => {
    e?.stopPropagation();
    const trimmed = renameValue.trim();
    if (!trimmed) return;
    setRenameLoading(true);
    try {
      const updated = await renameModule(moduleId, trimmed);
      setProjects((prev) =>
        prev.map((p) => (p.id === moduleId ? { ...p, name: updated.name } : p))
      );
      setRenamingId(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setRenameLoading(false);
    }
  };

  const requestDelete = (e, module) => {
    e.stopPropagation();
    setDeleteTarget({ id: module.id, name: module.name });
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await deleteModule(deleteTarget.id);
      setProjects((prev) => prev.filter((p) => p.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      setError(err.message);
      setDeleteTarget(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  const cancelDelete = () => setDeleteTarget(null);

  return (
    <div className="space-y-6">
      {/* Delete confirmation modal */}
      {deleteTarget && (
        <DeleteConfirmModal
          module={deleteTarget}
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
          loading={deleteLoading}
        />
      )}

      <div>
        <h1 className="text-2xl font-bold text-foreground">Modules</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse and manage all teaching modules
        </p>
      </div>

      <div className="rounded-lg bg-card border border-border p-4">
        <div className="flex gap-3 items-center">
          <SlidersHorizontal
            size={15}
            className="text-muted-foreground shrink-0"
          />
          <div className="relative flex-1">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by module name..."
              className="w-full pl-9 pr-4 py-2 bg-secondary border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {filtered.length} of {projects.length}
          </span>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-lg bg-card border border-border p-12 text-center">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg bg-card border border-border p-12 text-center">
          <Search
            size={32}
            className="mx-auto text-muted-foreground mb-3 opacity-50"
          />
          <p className="text-sm font-medium text-foreground">
            No modules found
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Try adjusting your filters or search term
          </p>
        </div>
      ) : (
        <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
          {filtered.map((project) => {
            const status = statusConfig[project.status] ?? {
              label: project.status || 'Unknown',
              classes: 'bg-secondary text-muted-foreground ring-1 ring-border',
            };
            const isRenaming = renamingId === project.id;

            return (
              <div
                key={project.id}
                onClick={() => {
                  if (!isRenaming)
                    router.push(`${APP_PATHS.modules}/${project.id}`);
                }}
                className="flex items-center gap-4 px-6 py-5 hover:bg-secondary/50 cursor-pointer transition-colors group"
              >
                {/* Name / rename input */}
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-center gap-3">
                    {isRenaming ? (
                      <input
                        ref={renameInputRef}
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') confirmRename(e, project.id);
                          if (e.key === 'Escape') cancelRename(e);
                        }}
                        className="text-sm font-semibold text-foreground bg-secondary border border-ring rounded px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-ring w-64"
                      />
                    ) : (
                      <span className="text-sm font-semibold text-foreground">
                        {project.name}
                      </span>
                    )}
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.classes}`}
                    >
                      {status.label}
                    </span>
                    {project.rubric_file ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-400">
                        <FileText size={11} />
                        Rubric attached
                      </span>
                    ) : (
                      <span className="text-xs text-amber-400">No rubric</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {project.academic_year && (
                      <>
                        <span>{project.academic_year}</span>
                        <span>·</span>
                      </>
                    )}
                    <span>
                      {project.project_count}{' '}
                      {project.project_count === 1 ? 'group' : 'groups'}
                    </span>
                    <span>·</span>
                    <span className="flex items-center gap-1.5">
                      <Users size={12} />
                      {project.student_count}{' '}
                      {project.student_count === 1 ? 'student' : 'students'}
                    </span>
                    {project.created_at && (
                      <>
                        <span>·</span>
                        <span>
                          Created{' '}
                          {new Date(project.created_at).toLocaleDateString(
                            'en-US',
                            { month: 'short', day: 'numeric', year: 'numeric' }
                          )}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Action buttons */}
                <div
                  className="flex items-center gap-1 shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  {isRenaming ? (
                    <>
                      <button
                        onClick={(e) => confirmRename(e, project.id)}
                        disabled={renameLoading}
                        title="Save name"
                        className="p-1.5 rounded text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                      >
                        <Check size={14} />
                      </button>
                      <button
                        onClick={cancelRename}
                        title="Cancel"
                        className="p-1.5 rounded text-muted-foreground hover:bg-secondary transition-colors"
                      >
                        <X size={14} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={(e) => startRename(e, project)}
                        title="Rename module"
                        className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-secondary opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        onClick={(e) => requestDelete(e, project)}
                        title="Delete module"
                        className="p-1.5 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 size={13} />
                      </button>
                    </>
                  )}
                </div>

                {!isRenaming && (
                  <ArrowRight
                    size={15}
                    className="text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all shrink-0"
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
