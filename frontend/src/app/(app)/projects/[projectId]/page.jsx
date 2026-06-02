'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Users, FileText, ArrowRight, ScanSearch, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { platformApi } from '@/lib/platformApi';

const mockGroups = [
  { id: 'group-1', name: 'Group 1', class: 'CS401-A', members: 4, assessmentProgress: 75, evidenceCount: 12 },
  { id: 'group-2', name: 'Group 2', class: 'CS401-A', members: 5, assessmentProgress: 40, evidenceCount: 8 },
];

function progressColor(pct) {
  if (pct >= 80) return 'bg-emerald-500';
  if (pct >= 50) return 'bg-primary';
  if (pct >= 25) return 'bg-amber-500';
  return 'bg-red-500';
}

export default function ProjectPage() {
  const { projectId } = useParams();
  const router = useRouter();
  const [groups, setGroups] = useState(mockGroups);
  const [moduleName, setModuleName] = useState('');
  const [loading, setLoading] = useState(true);
  const firstGroupId = groups[0]?.id || 'group-1';

  useEffect(() => {
    platformApi
      .getModule(projectId)
      .then((mod) => {
        setModuleName(mod.name);
        if (mod.projects?.length) {
          setGroups(
            mod.projects.map((p) => ({
              id: p.id,
              name: p.name,
              class: mod.academic_year || '—',
              members: p.students_count ?? 0,
              assessmentProgress: p.phase === 'prepare' || p.phase === 'grade' ? 70 : 25,
              evidenceCount: 0,
            }))
          );
        }
      })
      .catch(() => setGroups(mockGroups))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {moduleName || 'Project Groups'}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Select a group to view details and assess individual students
          </p>
        </div>
        <Link
          href={`/projects/${projectId}/groups/${firstGroupId}/overlaps`}
          className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-colors shrink-0"
        >
          <ScanSearch size={16} />
          Project overlaps
        </Link>
      </div>

      {loading ? (
        <div className="py-12 flex justify-center">
          <Loader2 className="animate-spin text-muted-foreground" size={24} />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {groups.map((group) => (
            <div
              key={group.id}
              onClick={() =>
                router.push(`/projects/${projectId}/groups/${group.id}`)
              }
              className="rounded-lg bg-card border border-border p-6 hover:border-primary/40 hover:bg-secondary/30 cursor-pointer transition-all group"
            >
              <div className="flex items-start justify-between mb-5">
                <div>
                  <h3 className="text-base font-semibold text-foreground">
                    {group.name}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {group.class}
                  </p>
                </div>
                <ArrowRight
                  size={16}
                  className="text-muted-foreground group-hover:text-primary transition-colors"
                />
              </div>
              <div className="flex items-center gap-5 mb-5 text-sm text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <Users size={14} />
                  <span>{group.members} students</span>
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-2 text-xs">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-semibold text-foreground">
                    {group.assessmentProgress}%
                  </span>
                </div>
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={`h-full rounded-full ${progressColor(group.assessmentProgress)}`}
                    style={{ width: `${group.assessmentProgress}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
