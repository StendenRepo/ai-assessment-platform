'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, FolderOpen } from 'lucide-react';
import { apiFetch } from '@/lib/apiFetch';

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

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch('/projects')
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const recent = projects.slice(0, 5);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Overview of all active group projects
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg bg-card border border-border p-5">
          <div className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
            Total Projects
          </div>
          <div className="text-3xl font-bold text-foreground">
            {loading ? '—' : projects.length}
          </div>
        </div>
        <div className="rounded-lg bg-card border border-border p-5">
          <div className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-3">
            Active Projects
          </div>
          <div className="text-3xl font-bold text-foreground">
            {loading
              ? '—'
              : projects.filter((p) => p.status === 'active').length}
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-foreground">
            Recent Projects
          </h2>
          <button
            onClick={() => router.push('/projects')}
            className="flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors"
          >
            View all <ArrowRight size={14} />
          </button>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!loading && recent.length === 0 && (
          <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
            <FolderOpen
              size={32}
              className="mx-auto mb-3 text-muted-foreground/50"
            />
            <p className="text-sm text-muted-foreground">No projects yet.</p>
            <button
              onClick={() => router.push('/projects/new')}
              className="mt-3 text-sm text-primary hover:text-primary/80 transition-colors"
            >
              Create your first project →
            </button>
          </div>
        )}

        {recent.length > 0 && (
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {recent.map((project) => {
              const s = statusConfig[project.status] ?? statusConfig.active;
              return (
                <div
                  key={project.id}
                  onClick={() => router.push(`/projects/${project.id}`)}
                  className="flex items-center gap-6 px-6 py-4 hover:bg-secondary/50 cursor-pointer transition-colors"
                >
                  <div className="w-2 h-2 rounded-full bg-primary shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-sm font-semibold text-foreground truncate">
                        {project.name}
                      </span>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${s.classes}`}
                      >
                        {s.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      {project.course && <span>{project.course}</span>}
                      {project.course && project.group_name && <span>·</span>}
                      {project.group_name && <span>{project.group_name}</span>}
                      {project.deadline && (
                        <>
                          {(project.course || project.group_name) && (
                            <span>·</span>
                          )}
                          <span>
                            Due{' '}
                            {new Date(project.deadline).toLocaleDateString(
                              'en-US',
                              {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                              }
                            )}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <ArrowRight
                    size={14}
                    className="text-muted-foreground shrink-0"
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
