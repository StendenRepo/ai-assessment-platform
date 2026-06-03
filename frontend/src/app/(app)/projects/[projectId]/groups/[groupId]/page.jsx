'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Upload, X, FileCode, CheckCircle2, Clock, Circle } from 'lucide-react';
import {
  getProject,
  listProjectGroups,
  listProjectStudents,
} from '@/lib/projectsApi';

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
  const { projectId, groupId } = useParams();
  const router = useRouter();
  const [moduleName, setModuleName] = useState('Module');
  const [groupName, setGroupName] = useState('Group');
  const [students, setStudents] = useState([]);
  const [loadingStudents, setLoadingStudents] = useState(true);
  const [studentsError, setStudentsError] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    let mounted = true;
    Promise.all([getProject(projectId), listProjectGroups(projectId)])
      .then(([project, groups]) => {
        if (!mounted) return;
        setModuleName(project?.name || 'Module');
        const selectedGroup = groups.find((group) => group.id === groupId);
        if (selectedGroup) {
          setGroupName(
            selectedGroup.name || selectedGroup.group_name || 'Group'
          );
        }
      })
      .catch(() => {
        if (!mounted) return;
        setModuleName('Module');
        setGroupName('Group');
      });

    listProjectStudents(projectId)
      .then((data) => {
        if (!mounted) return;
        setStudents(data.filter((student) => student.project_id === groupId));
        setStudentsError('');
      })
      .catch((e) => {
        if (mounted) setStudentsError(e.message);
      })
      .finally(() => {
        if (mounted) setLoadingStudents(false);
      });

    return () => {
      mounted = false;
    };
  }, [projectId, groupId]);

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
          {groupName} — {moduleName}
        </h1>
      </div>

      <div className="rounded-lg bg-card border border-border">
        <div className="grid grid-cols-3 divide-x divide-border">
          {[
            { label: 'Module', value: moduleName },
            { label: 'Group', value: groupName },
            { label: 'Students', value: String(students.length) },
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
            Students ({students.length})
          </h2>
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {loadingStudents ? (
              <div className="p-8 text-center">
                <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
              </div>
            ) : studentsError ? (
              <div className="p-8 text-center">
                <p className="text-sm font-medium text-red-400">
                  Failed to load students
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {studentsError}
                </p>
              </div>
            ) : students.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-sm font-medium text-foreground">
                  No students in this group yet
                </p>
              </div>
            ) : (
              students.map((student) => {
                const statusKey = student.assessment_status ?? 'not-started';
                const status =
                  assessmentStatusConfig[statusKey] ??
                  assessmentStatusConfig['not-started'];
                const StatusIcon = status.icon;
                return (
                  <div
                    key={student.id}
                    onClick={() =>
                      router.push(
                        `/modules/${projectId}/groups/${groupId}/students/${student.id}`
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
                        {student.student_number}
                      </div>
                    </div>
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
                          `/modules/${projectId}/groups/${groupId}/students/${student.id}`
                        );
                      }}
                      className="shrink-0 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
                    >
                      Assess
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="col-span-1">
          <div className="rounded-lg bg-card border border-border p-5 sticky top-4 space-y-5">
            <h3 className="text-sm font-semibold text-foreground">
              Evidence Files
            </h3>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground font-medium">
                Uploaded ({uploadedFiles.length})
              </p>
              <div className="space-y-1.5 max-h-52 overflow-y-auto">
                {uploadedFiles.length === 0 ? (
                  <div className="rounded-md bg-secondary border border-border px-3 py-3">
                    <p className="text-xs text-muted-foreground">
                      No files uploaded yet
                    </p>
                  </div>
                ) : (
                  uploadedFiles.map((file, i) => (
                    <div
                      key={`${file.name}-${i}`}
                      className="rounded-md bg-secondary border border-border px-3 py-2"
                    >
                      <div className="flex items-center gap-2">
                        <FileCode size={12} className="text-primary shrink-0" />
                        <span className="text-xs font-medium text-foreground truncate">
                          {file.name}
                        </span>
                      </div>
                    </div>
                  ))
                )}
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
