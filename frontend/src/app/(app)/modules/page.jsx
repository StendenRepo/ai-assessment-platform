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

  // Delete state
  const [deletingId, setDeletingId] = useState(null);

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

  const handleDelete = async (e, moduleId) => {
    e.stopPropagation();
    if (deletingId === moduleId) {
      // Second click — confirmed
      try {
        await deleteModule(moduleId);
        setProjects((prev) => prev.filter((p) => p.id !== moduleId));
      } catch (err) {
        setError(err.message);
      } finally {
        setDeletingId(null);
      }
    } else {
      // First click — ask for confirmation
      setDeletingId(moduleId);
    }
  };

  const cancelDelete = (e) => {
    e.stopPropagation();
    setDeletingId(null);
  };

  return (
    <div className="space-y-6">
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
            className="bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all"
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
            const isDeleting = deletingId === project.id;

            return (
              <div
                key={project.id}
                onClick={() => {
                  if (!isRenaming && !isDeleting)
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
                  ) : isDeleting ? (
                    <>
                      <span className="text-xs text-red-400 mr-1">
                        Delete?
                      </span>
                      <button
                        onClick={(e) => handleDelete(e, project.id)}
                        title="Confirm delete"
                        className="p-1.5 rounded text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <Check size={14} />
                      </button>
                      <button
                        onClick={cancelDelete}
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
                        onClick={(e) => handleDelete(e, project.id)}
                        title="Delete module"
                        className="p-1.5 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 size={13} />
                      </button>
                    </>
                  )}
                </div>

                {!isRenaming && !isDeleting && (
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
