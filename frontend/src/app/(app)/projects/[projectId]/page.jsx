'use client';

import { useParams, useRouter } from 'next/navigation';
import { Users, FileText, ArrowRight } from 'lucide-react';

const groups = [
  {
    id: 'group-1',
    name: 'Group 1',
    class: 'CS401-A',
    members: 4,
    assessmentProgress: 75,
    evidenceCount: 12,
  },
  {
    id: 'group-2',
    name: 'Group 2',
    class: 'CS401-A',
    members: 5,
    assessmentProgress: 40,
    evidenceCount: 8,
  },
  {
    id: 'group-3',
    name: 'Group 3',
    class: 'CS401-B',
    members: 4,
    assessmentProgress: 90,
    evidenceCount: 15,
  },
  {
    id: 'group-4',
    name: 'Group 4',
    class: 'CS401-B',
    members: 3,
    assessmentProgress: 25,
    evidenceCount: 5,
  },
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Project Groups</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Select a group to view details and assess individual students
        </p>
      </div>

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
                  Class: {group.class}
                </p>
              </div>
              <ArrowRight
                size={16}
                className="text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all"
              />
            </div>
            <div className="flex items-center gap-5 mb-5 text-sm">
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Users size={14} />
                <span>{group.members} students</span>
              </div>
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <FileText size={14} />
                <span>{group.evidenceCount} files</span>
              </div>
            </div>
            <div>
              <div className="flex justify-between mb-2 text-xs">
                <span className="text-muted-foreground">
                  Assessment progress
                </span>
                <span className="font-semibold text-foreground">
                  {group.assessmentProgress}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-secondary overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${progressColor(group.assessmentProgress)}`}
                  style={{ width: `${group.assessmentProgress}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
