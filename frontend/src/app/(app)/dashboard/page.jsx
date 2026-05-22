'use client';

import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  TrendingUp,
} from 'lucide-react';
import { mockProjects } from '@/lib/mockData';

const statusConfig = {
  active: {
    label: 'Active',
    classes: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
  },
  completed: {
    label: 'Completed',
    classes: 'bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/20',
  },
  overdue: {
    label: 'Overdue',
    classes: 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20',
  },
};

const statCards = [
  {
    label: 'Active Projects',
    value: '12',
    icon: TrendingUp,
    color: 'text-primary',
  },
  {
    label: 'Deadlines This Week',
    value: '3',
    icon: Clock,
    color: 'text-amber-400',
  },
  {
    label: 'Assessments Completed',
    value: '47',
    icon: CheckCircle2,
    color: 'text-emerald-400',
  },
  {
    label: 'Pending Review',
    value: '8',
    icon: AlertTriangle,
    color: 'text-orange-400',
  },
];

export default function DashboardPage() {
  const router = useRouter();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Overview of all active group projects
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="rounded-lg bg-card border border-border p-5"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                {card.label}
              </span>
              <card.icon size={15} className={card.color} />
            </div>
            <div className="text-3xl font-bold text-foreground">
              {card.value}
            </div>
          </div>
        ))}
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

        <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
          {mockProjects.map((project) => {
            const status = statusConfig[project.status];
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
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${status.classes}`}
                    >
                      {status.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span>{project.course}</span>
                    <span>·</span>
                    <span>Group {project.groupNumber}</span>
                    <span>·</span>
                    <span>
                      Due{' '}
                      {new Date(project.deadline).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </span>
                  </div>
                </div>
                <div className="w-36 shrink-0">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-muted-foreground">
                      Progress
                    </span>
                    <span className="text-xs font-semibold text-foreground">
                      {project.assessmentProgress}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${project.assessmentProgress}%` }}
                    />
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
      </div>
    </div>
  );
}
