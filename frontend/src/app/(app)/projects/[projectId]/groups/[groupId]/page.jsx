'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Upload,
  X,
  FileCode,
  CheckCircle2,
  Clock,
  Circle,
  ScanSearch,
  Loader2,
  Sparkles,
  Plus,
  Trash2,
} from 'lucide-react';
import Link from 'next/link';
import { platformApi } from '@/lib/platformApi';
import { inputCls, selectFullCls } from '@/lib/formStyles';

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

function studentStatus(s) {
  if (s.has_analysis) return 'completed';
  if (s.phase === 'prepare' || s.phase === 'grade' || s.phase === 'conduct')
    return 'in-progress';
  return 'not-started';
}

export default function GroupDetailPage() {
  const { projectId, groupId } = useParams();
  const router = useRouter();
  const [group, setGroup] = useState(null);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploadStudentId, setUploadStudentId] = useState('');
  const [pendingFiles, setPendingFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState('');
  const [analysisError, setAnalysisError] = useState(null);
  const [error, setError] = useState(null);
  const [newName, setNewName] = useState('');
  const [newNumber, setNewNumber] = useState('');
  const [addingStudent, setAddingStudent] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await platformApi.ensureGroup(projectId, groupId);
      const data = await platformApi.getGroup(projectId, groupId);
      setGroup(data);
      setStudents(data.students || []);
      setUploadStudentId((prev) => {
        if (prev && data.students?.some((s) => s.id === prev)) return prev;
        return data.students?.[0]?.id || '';
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [projectId, groupId]);

  useEffect(() => {
    load();
  }, [load]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      await platformApi.ensureGroup(projectId, groupId);
      await platformApi.runAnalysis(projectId, groupId, (s) => {
        setAnalysisStep(s.step || s.status || 'Running…');
      });
      setAnalysisStep('Analysis complete');
      await load();
    } catch (e) {
      setAnalysisError(e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const uploadFiles = async () => {
    if (!uploadStudentId || !pendingFiles.length) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of pendingFiles) {
        await platformApi.uploadEvidence(projectId, groupId, uploadStudentId, file);
      }
      setPendingFiles([]);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const addStudent = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setAddingStudent(true);
    try {
      await platformApi.addStudent(projectId, groupId, newName.trim(), newNumber.trim());
      setNewName('');
      setNewNumber('');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setAddingStudent(false);
    }
  };

  const removeStudent = async (studentId, e) => {
    e.stopPropagation();
    if (!confirm('Remove this student from the group?')) return;
    try {
      await platformApi.removeStudent(projectId, groupId, studentId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const removeEvidence = async (studentId, evidenceId, e) => {
    e.stopPropagation();
    try {
      await platformApi.removeEvidence(projectId, groupId, studentId, evidenceId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const allEvidence = students.flatMap((s) =>
    (s.evidence || []).map((ev) => ({ ...ev, studentName: s.name, studentId: s.id }))
  );

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files.length > 0) {
      setPendingFiles((f) => [...f, ...Array.from(e.dataTransfer.files)]);
    }
  };

  if (loading && !group) {
    return (
      <div className="py-16 flex justify-center">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href={`/projects/${projectId}`}
            className="text-xs text-muted-foreground hover:text-primary transition-colors"
          >
            ← Back to project
          </Link>
          <h1 className="text-2xl font-bold text-foreground mt-2">
            {group?.name || 'Group'}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {students.length} student{students.length !== 1 ? 's' : ''} · Phase{' '}
            {group?.phase || '—'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            type="button"
            onClick={runAnalysis}
            disabled={analyzing || students.length < 2}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-50"
          >
            {analyzing ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Sparkles size={16} />
            )}
            Run AI analysis
          </button>
          <Link
            href={`/projects/${projectId}/groups/${groupId}/overlaps`}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
          >
            <ScanSearch size={16} />
            Review overlaps
          </Link>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-2">
          {error}
        </p>
      )}
      {analysisStep && !analysisError && (
        <p className="text-xs text-muted-foreground">{analysisStep}</p>
      )}
      {analysisError && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-2">
          {analysisError}
        </p>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">
              Students ({students.length})
            </h2>
          </div>

          <form
            onSubmit={addStudent}
            className="rounded-lg bg-card border border-border p-4 flex flex-wrap items-end gap-2"
          >
            <div className="flex-1 min-w-[140px]">
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Name
              </label>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Student name"
                className={inputCls}
              />
            </div>
            <div className="w-36">
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Number
              </label>
              <input
                value={newNumber}
                onChange={(e) => setNewNumber(e.target.value)}
                placeholder="S2034567"
                className={inputCls}
              />
            </div>
            <button
              type="submit"
              disabled={addingStudent || !newName.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md border border-border text-sm font-semibold hover:bg-secondary disabled:opacity-50"
            >
              {addingStudent ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Plus size={14} />
              )}
              Add student
            </button>
          </form>

          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {students.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No students yet. Add a student or use demo fixtures via ensure.
              </p>
            ) : (
              students.map((student) => {
                const key = studentStatus(student);
                const status = assessmentStatusConfig[key];
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
                        {student.student_number || student.id} ·{' '}
                        {student.evidence_count ?? student.evidence?.length ?? 0}{' '}
                        files
                      </div>
                    </div>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ${status.classes}`}
                    >
                      <StatusIcon size={11} />
                      {status.label}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => removeStudent(student.id, e)}
                      className="p-1.5 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                      aria-label="Remove student"
                    >
                      <Trash2 size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(
                          `/projects/${projectId}/groups/${groupId}/students/${student.id}`
                        );
                      }}
                      className="shrink-0 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90"
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
          <div className="rounded-lg bg-card border border-border p-5 sticky top-4 space-y-4">
            <h3 className="text-sm font-semibold text-foreground">Evidence</h3>

            <div className="space-y-2 max-h-48 overflow-y-auto">
              <p className="text-xs text-muted-foreground font-medium">
                Uploaded ({allEvidence.length})
              </p>
              {allEvidence.length === 0 ? (
                <p className="text-xs text-muted-foreground py-2">No files yet</p>
              ) : (
                allEvidence.map((file) => (
                  <div
                    key={file.id}
                    className="rounded-md bg-secondary border border-border px-3 py-2 group"
                  >
                    <div className="flex items-center gap-2">
                      <FileCode size={12} className="text-primary shrink-0" />
                      <span className="text-xs font-medium text-foreground truncate flex-1">
                        {file.filename}
                      </span>
                      <button
                        type="button"
                        onClick={(e) =>
                          removeEvidence(file.studentId, file.id, e)
                        }
                        className="text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100"
                      >
                        <X size={12} />
                      </button>
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      {file.studentName}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="border-t border-border pt-4 space-y-3">
              <p className="text-xs font-medium text-muted-foreground">
                Upload for student
              </p>
              <select
                value={uploadStudentId}
                onChange={(e) => setUploadStudentId(e.target.value)}
                className={selectFullCls}
              >
                {students.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-lg p-4 text-center transition-all ${dragActive ? 'border-primary bg-primary/5' : 'border-border'}`}
              >
                <Upload size={18} className="mx-auto text-muted-foreground mb-2" />
                <p className="text-xs text-muted-foreground mb-2">Drop files</p>
                <input
                  type="file"
                  multiple
                  onChange={(e) => {
                    if (e.target.files) {
                      setPendingFiles((f) => [...f, ...Array.from(e.target.files)]);
                    }
                  }}
                  className="hidden"
                  id="evidence-upload"
                />
                <label
                  htmlFor="evidence-upload"
                  className="inline-block px-3 py-1 rounded-md border border-border text-xs cursor-pointer hover:bg-secondary"
                >
                  Browse
                </label>
              </div>
              {pendingFiles.length > 0 && (
                <div className="space-y-1">
                  {pendingFiles.map((file, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 text-xs text-foreground"
                    >
                      <FileCode size={12} className="text-primary shrink-0" />
                      <span className="truncate flex-1">{file.name}</span>
                      <button
                        type="button"
                        onClick={() =>
                          setPendingFiles((f) => f.filter((_, j) => j !== i))
                        }
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={uploadFiles}
                    disabled={uploading}
                    className="w-full mt-2 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold disabled:opacity-50"
                  >
                    {uploading ? 'Uploading…' : `Upload ${pendingFiles.length} file(s)`}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
