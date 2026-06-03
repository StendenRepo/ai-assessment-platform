'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowRight, CheckCircle2, Circle, Clock, Users } from 'lucide-react';
import {
  getProject,
  listProjectGroups,
  listProjectStudents,
} from '@/lib/modulesApi';
import { APP_PATHS } from '@/lib/routes';

const assessmentStatusConfig = {
  completed: {
    label: 'Completed',
    icon: CheckCircle2,
    classes: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
  },
  'in-progress': {
    label: 'In Progress',
    icon: Clock,
    classes: 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20',
  },
  'not-started': {
    label: 'Not Started',
    icon: Circle,
    classes: 'bg-secondary text-muted-foreground ring-1 ring-border',
  },
};

export default function GroupDetailPage() {
  const { moduleId, groupId } = useParams();
  const router = useRouter();

  const [module, setModule] = useState(null);
  const [group, setGroup] = useState(null);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    Promise.all([
      getProject(moduleId),
      listProjectGroups(moduleId),
      listProjectStudents(moduleId),
    ])
      .then(([mod, groups, allStudents]) => {
        setModule(mod);
        const found = groups.find((g) => g.id === groupId);
        if (!found) {
          setLoadError('Group not found.');
          return;
        }
        setGroup(found);
        setStudents(allStudents.filter((s) => s.project_id === groupId));
      })
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [moduleId, groupId]);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="rounded-lg bg-card border border-border p-12 text-center">
        <p className="text-sm font-medium text-red-400">{loadError}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{group.name}</h1>
        <p className="text-sm text-muted-foreground mt-1">{module.name}</p>
      </div>

      <div className="rounded-lg bg-card border border-border">
        <div className="grid grid-cols-3 divide-x divide-border">
          {[
            { label: 'Module', value: module.name },
            { label: 'Academic Year', value: module.academic_year || '—' },
            { label: 'Students', value: students.length },
          ].map((item) => (
            <div key={item.label} className="px-6 py-4">
              <div className="text-xs text-muted-foreground mb-1">
                {item.label}
              </div>
              <div className="text-sm font-semibold text-foreground">
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-base font-semibold text-foreground flex items-center gap-2 mb-3">
          <Users size={16} />
          Students ({students.length})
        </h2>

        {students.length === 0 ? (
          <div className="rounded-lg bg-card border border-border p-12 text-center">
            <Users
              size={28}
              className="mx-auto text-muted-foreground mb-3 opacity-50"
            />
            <p className="text-sm font-medium text-foreground">
              No students in this group
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Assign students to this group from the module page.
            </p>
          </div>
        ) : (
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {students.map((student) => {
              const statusCfg =
                assessmentStatusConfig[student.assessment_status] ??
                assessmentStatusConfig['not-started'];
              const StatusIcon = statusCfg.icon;
              return (
                <div
                  key={student.id}
                  onClick={() =>
                    router.push(
                      `${APP_PATHS.modules}/${moduleId}/groups/${groupId}/students/${student.id}`
                    )
                  }
                  className="flex items-center gap-4 px-5 py-4 hover:bg-secondary/50 cursor-pointer transition-colors group"
                >
                  <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary shrink-0">
                    {student.name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')
                      .slice(0, 2)
                      .toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-foreground">
                      {student.name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5 font-mono">
                      {student.student_number}
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ${statusCfg.classes}`}
                  >
                    <StatusIcon size={11} />
                    {statusCfg.label}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(
                        `${APP_PATHS.modules}/${moduleId}/groups/${groupId}/students/${student.id}`
                      );
                    }}
                    className="shrink-0 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
                  >
                    Assess
                  </button>
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
