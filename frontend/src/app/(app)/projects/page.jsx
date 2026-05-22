'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Search, ArrowRight, SlidersHorizontal } from 'lucide-react';
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

export default function ProjectsPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [courseFilter, setCourseFilter] = useState('all');

  const filtered = mockProjects.filter((p) => {
    const matchSearch =
      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.course.toLowerCase().includes(searchTerm.toLowerCase());
    const matchStatus = statusFilter === 'all' || p.status === statusFilter;
    const matchCourse = courseFilter === 'all' || p.course === courseFilter;
    return matchSearch && matchStatus && matchCourse;
  });

  const courses = Array.from(new Set(mockProjects.map((p) => p.course)));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Projects</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse and manage all group projects
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
              placeholder="Search by project name or course..."
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
            <option value="overdue">Overdue</option>
          </select>
          <select
            value={courseFilter}
            onChange={(e) => setCourseFilter(e.target.value)}
            className="bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all"
          >
            <option value="all">All Courses</option>
            {courses.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {filtered.length} of {mockProjects.length}
          </span>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg bg-card border border-border p-12 text-center">
          <Search
            size={32}
            className="mx-auto text-muted-foreground mb-3 opacity-50"
          />
          <p className="text-sm font-medium text-foreground">
            No projects found
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Try adjusting your filters or search term
          </p>
        </div>
      ) : (
        <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
          {filtered.map((project) => {
            const status = statusConfig[project.status];
            return (
              <div
                key={project.id}
                onClick={() => router.push(`/projects/${project.id}`)}
                className="flex items-center gap-6 px-6 py-5 hover:bg-secondary/50 cursor-pointer transition-colors group"
              >
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-foreground">
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
                <div className="w-40 shrink-0">
                  <div className="flex justify-between mb-1.5 text-xs">
                    <span className="text-muted-foreground">Assessment</span>
                    <span className="font-semibold text-foreground">
                      {project.assessmentProgress}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${project.assessmentProgress}%` }}
                    />
                  </div>
                </div>
                <ArrowRight
                  size={15}
                  className="text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all shrink-0"
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
