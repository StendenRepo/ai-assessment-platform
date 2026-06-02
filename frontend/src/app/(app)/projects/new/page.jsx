'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Upload, X, Plus, FileText, Loader2 } from 'lucide-react';
import { platformApi } from '@/lib/platformApi';
import { inputCls } from '@/lib/formStyles';

export default function NewProjectPage() {
  const router = useRouter();
  const [projectName, setProjectName] = useState('');
  const [course, setCourse] = useState('');
  const [className, setClassName] = useState('');
  const [deadline, setDeadline] = useState('');
  const [description, setDescription] = useState('');
  const [students, setStudents] = useState([{ email: '', studentNumber: '' }]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  const updateStudent = (i, field, val) => {
    const updated = [...students];
    updated[i][field] = val;
    setStudents(updated);
  };

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

  const createProject = async () => {
    if (!projectName.trim()) {
      setError('Project name is required');
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const mod = await platformApi.createModule(
        projectName.trim(),
        course.trim() || className.trim() || '2025-2026'
      );
      const moduleId = mod.id;
      const group = await platformApi.createGroup(
        moduleId,
        className.trim() || 'Group 1'
      );
      const groupId = group.id;

      const validStudents = students.filter(
        (s) => s.email.trim() || s.studentNumber.trim()
      );
      let firstStudentId = null;
      for (const s of validStudents) {
        const name =
          s.email.split('@')[0]?.replace(/\./g, ' ') ||
          `Student ${s.studentNumber || '?'}`;
        const added = await platformApi.addStudent(
          moduleId,
          groupId,
          name,
          s.studentNumber || ''
        );
        if (!firstStudentId) firstStudentId = added.id;
      }

      if (uploadedFiles.length > 0 && firstStudentId) {
        for (const file of uploadedFiles) {
          await platformApi.uploadEvidence(
            moduleId,
            groupId,
            firstStudentId,
            file
          );
        }
      }

      await platformApi.ensureGroup(moduleId, groupId).catch(() => {});

      router.push(`/projects/${moduleId}/criteria`);
    } catch (e) {
      setError(e.message);
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          Create New Project
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Creates a module and group in the POC backend, then opens criteria setup
        </p>
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-2">
          {error}
        </p>
      )}

      <div className="max-w-3xl space-y-5">
        <div className="rounded-lg bg-card border border-border p-6 space-y-5">
          <h2 className="text-sm font-semibold text-foreground">
            Project Information
          </h2>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Project Name *
            </label>
            <input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="e.g. E-Commerce Platform"
              className={inputCls}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Course / academic year
              </label>
              <input
                value={course}
                onChange={(e) => setCourse(e.target.value)}
                placeholder="e.g. 2025-2026"
                className={inputCls}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Group name
              </label>
              <input
                value={className}
                onChange={(e) => setClassName(e.target.value)}
                placeholder="e.g. Group 1"
                className={inputCls}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Deadline (display only)
            </label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className={inputCls}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Brief description of the project..."
              className={`${inputCls} resize-none`}
            />
          </div>
        </div>

        <div className="rounded-lg bg-card border border-border p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Students</h2>
            <button
              type="button"
              onClick={() =>
                setStudents([...students, { email: '', studentNumber: '' }])
              }
              className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors"
            >
              <Plus size={13} /> Add student
            </button>
          </div>
          <div className="space-y-2.5">
            {students.map((student, i) => (
              <div key={i} className="flex gap-2.5">
                <input
                  value={student.studentNumber}
                  onChange={(e) =>
                    updateStudent(i, 'studentNumber', e.target.value)
                  }
                  placeholder="Student Number"
                  className="w-44 bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all font-mono"
                />
                <input
                  type="email"
                  value={student.email}
                  onChange={(e) => updateStudent(i, 'email', e.target.value)}
                  placeholder="student@university.edu"
                  className="flex-1 bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-all"
                />
                {students.length > 1 && (
                  <button
                    type="button"
                    onClick={() =>
                      setStudents(students.filter((_, j) => j !== i))
                    }
                    className="text-muted-foreground hover:text-foreground transition-colors p-2"
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg bg-card border border-border p-6 space-y-4">
          <h2 className="text-sm font-semibold text-foreground">
            Evidence Sources
          </h2>
          <p className="text-xs text-muted-foreground">
            Files upload to the first student after creation
          </p>
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-lg p-10 text-center transition-all ${dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'}`}
          >
            <Upload size={28} className="mx-auto text-muted-foreground mb-3" />
            <p className="text-sm font-medium text-foreground mb-1">
              Drop files here to upload
            </p>
            <p className="text-xs text-muted-foreground mb-4">
              Code files, documents, PDFs, images · Max 100 MB per file
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
              id="file-upload"
            />
            <label
              htmlFor="file-upload"
              className="inline-block px-4 py-2 rounded-md border border-border text-sm font-medium text-foreground cursor-pointer hover:bg-secondary transition-all"
            >
              Browse files
            </label>
          </div>
          {uploadedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                Queued ({uploadedFiles.length})
              </p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {uploadedFiles.map((file, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-md bg-secondary border border-border px-3 py-2.5"
                  >
                    <FileText size={14} className="text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-foreground truncate">
                        {file.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {(file.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setUploadedFiles((f) => f.filter((_, j) => j !== i))
                      }
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end">
          <button
            type="button"
            disabled={creating}
            onClick={() => router.push('/projects')}
            className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={creating}
            onClick={createProject}
            className="flex items-center gap-2 px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : null}
            Create Project →
          </button>
        </div>
      </div>
    </div>
  );
}
