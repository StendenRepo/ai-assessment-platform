'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  TrendingUp,
} from 'lucide-react';
import { listModules, listProjectStudents } from '@/lib/modulesApi';
import { APP_PATHS } from '@/lib/routes';

const statusConfig = {
  active: {
    label: 'Active',
    classes: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
  },
  archived: {
    label: 'Archived',
    classes: 'bg-secondary text-muted-foreground ring-1 ring-border',
  },
};

export default function DashboardPage() {
  const router = useRouter();
  const [modules, setModules] = useState([]);
  const [pendingReviewCount, setPendingReviewCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    let running = false;

    const refreshDashboard = async () => {
      if (running) return;
      running = true;
      try {
        const moduleList = await listModules();
        const studentLists = await Promise.all(
          moduleList.map((module) => listProjectStudents(module.id))
        );

        const pendingCount = studentLists.reduce(
          (sum, students) =>
            sum +
            students.filter(
              (student) => student.assessment_status === 'in-progress'
            ).length,
          0
        );

        if (!mounted) return;
        setModules(moduleList);
        setPendingReviewCount(pendingCount);
        setError('');
      } catch (e) {
        if (mounted) setError(e.message);
      } finally {
        if (mounted) setLoading(false);
        running = false;
      }
    };

    refreshDashboard();
    const intervalId = setInterval(refreshDashboard, 30000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
    };
  }, []);

  const activeModules = useMemo(
    () => modules.filter((module) => module.status === 'active').length,
    [modules]
  );

  const totalGroups = useMemo(
    () => modules.reduce((sum, module) => sum + (module.project_count ?? 0), 0),
    [modules]
  );

  const totalStudents = useMemo(
    () => modules.reduce((sum, module) => sum + (module.student_count ?? 0), 0),
    [modules]
  );

  const statCards = [
    {
      label: 'Active Modules',
      value: String(activeModules),
      icon: TrendingUp,
      color: 'text-primary',
    },
    {
      label: 'Module Groups',
      value: String(totalGroups),
      icon: Clock,
      color: 'text-amber-400',
    },
    {
      label: 'Students Enrolled',
      value: String(totalStudents),
      icon: CheckCircle2,
      color: 'text-emerald-400',
    },
    {
      label: 'Pending Review',
      value: String(pendingReviewCount),
      icon: AlertTriangle,
      color: 'text-orange-400',
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Overview of all active modules
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-lg bg-card border border-border p-5"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                  {card.label}
                </span>
                <Icon size={15} className={card.color} />
              </div>
              <div className="text-3xl font-bold text-foreground">
                {card.value}
              </div>
            </div>
          );
        })}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-foreground">
            Recent Modules
          </h2>
          <button
            onClick={() => router.push(APP_PATHS.modules)}
            className="flex items-center gap-1.5 text-sm text-primary hover:text-primary/80 transition-colors cursor-pointer"
          >
            View all <ArrowRight size={14} />
          </button>
        </div>

        {loading ? (
          <div className="rounded-lg bg-card border border-border p-12 text-center">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          </div>
        ) : error ? (
          <div className="rounded-lg bg-card border border-border p-12 text-center">
            <p className="text-sm font-medium text-red-400">
              Failed to load modules
            </p>
            <p className="text-xs text-muted-foreground mt-1">{error}</p>
          </div>
        ) : modules.length === 0 ? (
          <div className="rounded-lg bg-card border border-border p-12 text-center">
            <p className="text-sm font-medium text-foreground">
              No modules yet
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Create your first module to get started.
            </p>
          </div>
        ) : (
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {modules.map((module) => {
              const status = statusConfig[module.status] ?? {
                label: module.status || 'Unknown',
                classes:
                  'bg-secondary text-muted-foreground ring-1 ring-border',
              };
              return (
                <div
                  key={module.id}
                  onClick={() =>
                    router.push(`${APP_PATHS.modules}/${module.id}`)
                  }
                  className="flex items-center gap-6 px-6 py-4 hover:bg-secondary/50 cursor-pointer transition-colors"
                >
                  <div className="w-2 h-2 rounded-full bg-primary shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-sm font-semibold text-foreground truncate">
                        {module.name}
                      </span>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.classes}`}
                      >
                        {status.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      {module.academic_year && (
                        <span>{module.academic_year}</span>
                      )}
                      {module.academic_year && <span>·</span>}
                      <span>
                        {module.project_count} group
                        {module.project_count === 1 ? '' : 's'}
                      </span>
                      <span>·</span>
                      <span>
                        {module.student_count} student
                        {module.student_count === 1 ? '' : 's'}
                      </span>
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
