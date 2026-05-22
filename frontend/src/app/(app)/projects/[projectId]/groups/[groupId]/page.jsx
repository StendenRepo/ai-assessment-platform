'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Upload, X, FileCode, CheckCircle2, Clock, Circle } from 'lucide-react';
import { mockStudents } from '@/lib/mockData';

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

const evidenceFiles = [
  {
    id: '1',
    name: 'auth.tsx',
    type: 'Code',
    uploadedBy: 'Lisa Anderson',
    date: '2026-05-10',
  },
  {
    id: '2',
    name: 'API-docs.md',
    type: 'Documentation',
    uploadedBy: 'Thomas Johnson',
    date: '2026-05-12',
  },
  {
    id: '3',
    name: 'demo-slides.pdf',
    type: 'Presentation',
    uploadedBy: 'Maya Patel',
    date: '2026-05-14',
  },
  {
    id: '4',
    name: 'database-schema.sql',
    type: 'Code',
    uploadedBy: 'Mark Davis',
    date: '2026-05-11',
  },
];

const group = {
  name: 'Group 1',
  class: 'CS401-A',
  projectName: 'E-Commerce Platform',
  course: 'Advanced Web Development',
  deadline: '2026-06-15',
};

export default function GroupDetailPage() {
  const { projectId, groupId } = useParams();
  const router = useRouter();
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files.length > 0)
      setUploadedFiles((f) => [...f, ...Array.from(e.dataTransfer.files)]);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          {group.name} — {group.projectName}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {group.course} · Class {group.class}
        </p>
      </div>

      <div className="rounded-lg bg-card border border-border">
        <div className="grid grid-cols-3 divide-x divide-border">
          {[
            { label: 'Class', value: group.class },
            { label: 'Project', value: group.projectName },
            {
              label: 'Deadline',
              value: new Date(group.deadline).toLocaleDateString('en-US', {
                day: 'numeric',
                month: 'long',
                year: 'numeric',
              }),
            },
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

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-3">
          <h2 className="text-base font-semibold text-foreground">
            Students ({mockStudents.length})
          </h2>
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {mockStudents.map((student) => {
              const status = assessmentStatusConfig[student.assessmentStatus];
              const StatusIcon = status.icon;
              return (
                <div
                  key={student.id}
                  onClick={() =>
                    router.push(
                      `/projects/${projectId}/groups/${groupId}/students/${student.id}`
                    )
                  }
                  className="flex items-center gap-4 px-5 py-4 hover:bg-secondary/50 cursor-pointer transition-colors group"
                >
                  <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-xs font-bold text-primary shrink-0">
                    {student.name
                      .split(' ')
                      .map((n) => n[0])
                      .join('')}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-foreground">
                      {student.name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {student.studentNumber} · {student.email}
                    </div>
                  </div>
                  {student.overallScore && (
                    <div className="text-right shrink-0">
                      <div className="text-xs text-muted-foreground mb-0.5">
                        Grade
                      </div>
                      <div className="text-xl font-bold text-foreground font-mono">
                        {student.overallScore}
                      </div>
                    </div>
                  )}
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ${status.classes}`}
                  >
                    <StatusIcon size={11} />
                    {status.label}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(
                        `/projects/${projectId}/groups/${groupId}/students/${student.id}`
                      );
                    }}
                    className="shrink-0 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
                  >
                    Assess
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        <div className="col-span-1">
          <div className="rounded-lg bg-card border border-border p-5 sticky top-4 space-y-5">
            <h3 className="text-sm font-semibold text-foreground">
              Evidence Files
            </h3>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground font-medium">
                Uploaded ({evidenceFiles.length})
              </p>
              <div className="space-y-1.5 max-h-52 overflow-y-auto">
                {evidenceFiles.map((file) => (
                  <div
                    key={file.id}
                    className="rounded-md bg-secondary border border-border px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <FileCode size={12} className="text-primary shrink-0" />
                      <span className="text-xs font-medium text-foreground truncate">
                        {file.name}
                      </span>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      {file.type} · {file.uploadedBy}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="border-t border-border pt-4 space-y-3">
              <p className="text-xs font-medium text-muted-foreground">
                Add Evidence
              </p>
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-lg p-5 text-center transition-all ${dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'}`}
              >
                <Upload
                  size={20}
                  className="mx-auto text-muted-foreground mb-2"
                />
                <p className="text-xs text-muted-foreground mb-2">
                  Drop files here
                </p>
                <input
                  type="file"
                  multiple
                  onChange={(e) => {
                    if (e.target.files)
                      setUploadedFiles((f) => [
                        ...f,
                        ...Array.from(e.target.files),
                      ]);
                  }}
                  className="hidden"
                  id="evidence-upload"
                />
                <label
                  htmlFor="evidence-upload"
                  className="inline-block px-3 py-1 rounded-md border border-border text-xs text-muted-foreground cursor-pointer hover:bg-secondary hover:text-foreground transition-all"
                >
                  Browse files
                </label>
              </div>
              {uploadedFiles.length > 0 && (
                <div className="space-y-1.5">
                  {uploadedFiles.map((file, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 rounded-md bg-secondary px-3 py-2"
                    >
                      <FileCode size={12} className="text-primary shrink-0" />
                      <span className="flex-1 text-xs text-foreground truncate">
                        {file.name}
                      </span>
                      <button
                        onClick={() =>
                          setUploadedFiles((f) => f.filter((_, j) => j !== i))
                        }
                        className="text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
