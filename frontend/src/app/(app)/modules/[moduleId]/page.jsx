'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  FolderPlus,
  RefreshCw,
  Trash2,
  UserCheck,
  UserPlus,
  Users,
  Upload,
} from 'lucide-react';
import {
  getProject,
  listProjectGroups,
  listProjectStudents,
  addProjectStudent,
  importProjectStudents,
  createProjectGroup,
  moveStudentToGroup,
  uploadRubric,
  deleteRubric,
} from '@/lib/modulesApi';
import { APP_PATHS } from '@/lib/routes';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

const ALLOWED_RUBRIC_LABEL = 'PDF or Excel (.xlsx)';

function formatBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export default function ModulePage() {
  const { moduleId } = useParams();
  const router = useRouter();

  const [project, setProject] = useState(null);
  const [students, setStudents] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [name, setName] = useState('');
  const [studentNumber, setStudentNumber] = useState('');
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const [groupName, setGroupName] = useState('');
  const [groupSubmitting, setGroupSubmitting] = useState(false);
  const [groupError, setGroupError] = useState('');

  const [assignStudentId, setAssignStudentId] = useState('');
  const [assignGroupId, setAssignGroupId] = useState('');
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState('');

  const fileInputRef = useRef(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importError, setImportError] = useState('');

  const rubricInputRef = useRef(null);
  const [uploadingRubric, setUploadingRubric] = useState(false);
  const [deletingRubric, setDeletingRubric] = useState(false);
  const [rubricDragActive, setRubricDragActive] = useState(false);
  const [rubricError, setRubricError] = useState('');

  useEffect(() => {
    Promise.all([
      getProject(moduleId),
      listProjectStudents(moduleId),
      listProjectGroups(moduleId),
    ])
      .then(([proj, list, groupList]) => {
        setProject(proj);
        setStudents(list);
        setGroups(groupList);
      })
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [moduleId]);

  const handleAdd = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!name.trim() || !studentNumber.trim()) {
      setFormError('Both name and student number are required.');
      return;
    }
    setSubmitting(true);
    try {
      const student = await addProjectStudent(moduleId, {
        name: name.trim(),
        student_number: studentNumber.trim(),
        project_id: selectedGroupId || null,
      });
      setStudents((prev) =>
        [...prev, student].sort((a, b) => a.name.localeCompare(b.name))
      );
      setName('');
      setStudentNumber('');
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportError('');
    setImportResult(null);
    try {
      const result = await importProjectStudents(
        moduleId,
        file,
        selectedGroupId
      );
      setImportResult(result);
      if (result.students?.length) {
        setStudents((prev) =>
          [...prev, ...result.students].sort((a, b) =>
            a.name.localeCompare(b.name)
          )
        );
      }
    } catch (err) {
      setImportError(err.message);
    } finally {
      setImporting(false);
      e.target.value = ''; // allow re-selecting the same file
    }
  };

  const handleAssign = async (e) => {
    e.preventDefault();
    setAssignError('');
    if (!assignStudentId || !assignGroupId) {
      setAssignError('Select both a student and a group.');
      return;
    }
    setAssigning(true);
    try {
      const updated = await moveStudentToGroup(
        moduleId,
        assignStudentId,
        assignGroupId
      );
      setStudents((prev) =>
        prev.map((s) =>
          s.id === assignStudentId
            ? { ...s, project_id: updated.project_id }
            : s
        )
      );
      setAssignStudentId('');
      setAssignGroupId('');
    } catch (err) {
      setAssignError(err.message);
    } finally {
      setAssigning(false);
    }
  };

  const handleMoveStudent = async (studentId, newProjectId) => {
    try {
      const updated = await moveStudentToGroup(
        moduleId,
        studentId,
        newProjectId
      );
      setStudents((prev) =>
        prev.map((s) =>
          s.id === studentId ? { ...s, project_id: updated.project_id } : s
        )
      );
    } catch {
      // keep existing state on failure
    }
  };

  const handleCreateGroup = async (e) => {
    e.preventDefault();
    setGroupError('');
    if (!groupName.trim()) {
      setGroupError('Group name is required.');
      return;
    }
    setGroupSubmitting(true);
    try {
      const group = await createProjectGroup(moduleId, {
        name: groupName.trim(),
      });
      setGroups((prev) => [group, ...prev]);
      setGroupName('');
      setSelectedGroupId(group.id);
    } catch (err) {
      setGroupError(err.message);
    } finally {
      setGroupSubmitting(false);
    }
  };

  const handleRubricFile = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'xlsx') {
      setRubricError(
        `Only PDF and Excel files are allowed. "${file.name}" is not supported.`
      );
      return;
    }
    setRubricError('');
    setUploadingRubric(true);
    try {
      const updated = await uploadRubric(moduleId, file);
      setProject((prev) => ({ ...prev, rubric_file: updated.rubric_file }));
    } catch (err) {
      setRubricError(err.message);
    } finally {
      setUploadingRubric(false);
      if (rubricInputRef.current) rubricInputRef.current.value = '';
    }
  };

  const handleRubricDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setRubricDragActive(false);
    handleRubricFile(e.dataTransfer.files?.[0]);
  };

  const handleRubricDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setRubricDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleRubricDelete = async () => {
    if (!confirm('Remove the rubric from this module?')) return;
    setRubricError('');
    setDeletingRubric(true);
    try {
      await deleteRubric(moduleId);
      setProject((prev) => ({ ...prev, rubric_file: null }));
    } catch (err) {
      setRubricError(err.message);
    } finally {
      setDeletingRubric(false);
    }
  };

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
        <p className="text-sm font-medium text-red-400">
          Failed to load module
        </p>
        <p className="text-xs text-muted-foreground mt-1">{loadError}</p>
      </div>
    );
  }

  const rubric = project?.rubric_file;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{project?.name}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage the students in this module to set up the assessment
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          <div className="space-y-3">
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
              <FolderPlus size={16} />
              Groups ({groups.length})
            </h2>

            {groups.length === 0 ? (
              <div className="rounded-lg bg-card border border-border p-10 text-center">
                <FolderPlus
                  size={28}
                  className="mx-auto text-muted-foreground mb-3 opacity-50"
                />
                <p className="text-sm font-medium text-foreground">
                  No groups yet
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Create a project group or keep using the default individual
                  student group.
                </p>
              </div>
            ) : (
              <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
                {groups.map((group) => (
                  <button
                    key={group.id}
                    type="button"
                    onClick={() =>
                      router.push(
                        `${APP_PATHS.modules}/${moduleId}/groups/${group.id}`
                      )
                    }
                    className="w-full flex items-center justify-between gap-4 px-5 py-4 hover:bg-secondary/50 text-left transition-colors"
                  >
                    <div>
                      <div className="text-sm font-semibold text-foreground">
                        {group.name}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground mt-2">
                        <span className="flex items-center gap-1.5 leading-none">
                          <Users size={13} />
                          {group.student_count}{' '}
                          {group.student_count === 1 ? 'student' : 'students'}
                        </span>
                        <span className="flex items-center gap-1.5 leading-none">
                          <FileText size={13} />
                          {group.file_count ?? 0}{' '}
                          {(group.file_count ?? 0) === 1 ? 'file' : 'files'}
                        </span>
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      Open group →
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
              <Users size={16} />
              Students ({students.length})
            </h2>

            {students.length === 0 ? (
              <div className="rounded-lg bg-card border border-border p-10 text-center">
                <Users
                  size={28}
                  className="mx-auto text-muted-foreground mb-3 opacity-50"
                />
                <p className="text-sm font-medium text-foreground">
                  No students yet
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Add students using the form to set up the assessment
                </p>
              </div>
            ) : (
              <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
                {students.map((student) => (
                  <div
                    key={student.id}
                    onClick={() =>
                      router.push(
                        `${APP_PATHS.modules}/${moduleId}/groups/${student.project_id}/students/${student.id}?from=module`
                      )
                    }
                    className="flex items-center gap-4 px-5 py-4 hover:bg-secondary/50 cursor-pointer transition-colors"
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
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="col-span-1 space-y-6">
          <div className="space-y-3">
            <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
              <FileText size={16} />
              Rubric File
            </h3>
            <div className="rounded-lg bg-card border border-border px-5 pt-5 pb-0 space-y-4">
              <p className="text-xs text-muted-foreground">
                Attach a rubric so the AI knows the grading criteria for this
                module. Only{' '}
                <span className="font-semibold text-foreground">PDF</span> or{' '}
                <span className="font-semibold text-foreground">Excel</span>{' '}
                (.xlsx) files are accepted.
              </p>

              {rubric ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 rounded-lg bg-secondary border border-border px-3 py-3">
                    <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      <FileText size={16} className="text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-foreground truncate">
                          {rubric.file_name || 'rubric'}
                        </span>
                        <CheckCircle2
                          size={13}
                          className="text-emerald-400 shrink-0"
                        />
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                        {rubric.file_type && (
                          <span className="uppercase font-mono">
                            {rubric.file_type}
                          </span>
                        )}
                        {rubric.size_bytes && (
                          <span>{formatBytes(rubric.size_bytes)}</span>
                        )}
                        {rubric.uploaded_at && (
                          <span>Uploaded {formatDate(rubric.uploaded_at)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-center gap-2">
                    <button
                      type="button"
                      onClick={() => rubricInputRef.current?.click()}
                      disabled={uploadingRubric}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card transition-all disabled:opacity-50"
                    >
                      <RefreshCw size={12} /> Replace
                    </button>
                    <button
                      type="button"
                      onClick={handleRubricDelete}
                      disabled={deletingRubric}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-destructive/30 text-xs font-medium text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50"
                    >
                      <Trash2 size={12} />{' '}
                      {deletingRubric ? 'Removing…' : 'Remove'}
                    </button>
                  </div>
                  <input
                    ref={rubricInputRef}
                    type="file"
                    accept=".pdf,.xlsx"
                    onChange={(e) => handleRubricFile(e.target.files?.[0])}
                    className="hidden"
                  />
                </div>
              ) : (
                <div
                  onDragEnter={handleRubricDrag}
                  onDragLeave={handleRubricDrag}
                  onDragOver={handleRubricDrag}
                  onDrop={handleRubricDrop}
                  className={`border-2 border-dashed rounded-lg p-6 text-center transition-all ${
                    rubricDragActive
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/40'
                  }`}
                >
                  <Upload
                    size={24}
                    className="mx-auto text-muted-foreground mb-2"
                  />
                  <p className="text-sm font-medium text-foreground mb-1">
                    {uploadingRubric ? 'Uploading…' : 'Drop your rubric here'}
                  </p>
                  <p className="text-xs text-muted-foreground mb-3">
                    <span className="font-semibold text-foreground">PDF</span>{' '}
                    or{' '}
                    <span className="font-semibold text-foreground">Excel</span>{' '}
                    (.xlsx) only
                  </p>
                  <input
                    ref={rubricInputRef}
                    type="file"
                    accept=".pdf,.xlsx"
                    onChange={(e) => handleRubricFile(e.target.files?.[0])}
                    className="hidden"
                    id="rubric-upload"
                  />
                  <label
                    htmlFor="rubric-upload"
                    className={`inline-block px-4 py-2 rounded-md border border-border text-sm font-medium text-foreground cursor-pointer hover:bg-secondary transition-all ${
                      uploadingRubric ? 'opacity-50 pointer-events-none' : ''
                    }`}
                  >
                    Browse files
                  </label>
                </div>
              )}

              {rubricError && (
                <div className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
                  {rubricError}
                </div>
              )}
            </div>
          </div>

          <form
            onSubmit={handleCreateGroup}
            className="rounded-lg bg-card border border-border p-5 space-y-4"
          >
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <FolderPlus size={15} />
              Add Group
            </h3>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Group name *
              </label>
              <input
                value={groupName}
                onChange={(e) => setGroupName(e.target.value)}
                placeholder="e.g. Group 1"
                className={inputClass}
              />
            </div>
            {groupError && <p className="text-xs text-red-400">{groupError}</p>}
            <button
              type="submit"
              disabled={groupSubmitting}
              className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {groupSubmitting ? 'Creating…' : 'Create Group'}
            </button>
          </form>
          <form
            onSubmit={handleAdd}
            className="rounded-lg bg-card border border-border p-5 sticky top-4 space-y-4"
          >
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <UserPlus size={15} />
              Add Student
            </h3>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Name *
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Lisa Anderson"
                className={inputClass}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Student Number *
              </label>
              <input
                value={studentNumber}
                onChange={(e) => setStudentNumber(e.target.value)}
                placeholder="e.g. S2034567"
                className={`${inputClass} font-mono`}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Group (optional)
              </label>
              <select
                value={selectedGroupId}
                onChange={(e) => setSelectedGroupId(e.target.value)}
                className={inputClass}
              >
                <option value="">Default individual group</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </div>
            {formError && <p className="text-xs text-red-400">{formError}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting ? 'Adding…' : 'Add Student'}
            </button>
          </form>

          <div className="rounded-lg bg-card border border-border p-5 space-y-3">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <FileSpreadsheet size={15} />
              Import from file
            </h3>
            <p className="text-xs text-muted-foreground">
              Upload an Excel (.xlsx) or CSV file with{' '}
              <span className="font-medium text-foreground">Name</span> and{' '}
              <span className="font-medium text-foreground">
                Student Number
              </span>{' '}
              columns.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.csv"
              onChange={handleImport}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={importing}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md border border-border bg-secondary text-sm font-semibold text-foreground hover:bg-secondary/70 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Upload size={15} />
              {importing ? 'Importing…' : 'Choose file'}
            </button>

            {importError && (
              <p className="text-xs text-red-400">{importError}</p>
            )}

            {importResult && (
              <div className="space-y-2 pt-1">
                <p className="text-xs font-medium text-emerald-400">
                  Imported {importResult.imported_count} of{' '}
                  {importResult.total_rows}{' '}
                  {importResult.total_rows === 1 ? 'row' : 'rows'}.
                </p>
                {importResult.error_count > 0 && (
                  <div className="rounded-md border border-border bg-secondary/50 p-3 space-y-1 max-h-48 overflow-y-auto">
                    <p className="text-xs font-medium text-amber-400">
                      {importResult.error_count}{' '}
                      {importResult.error_count === 1 ? 'row' : 'rows'} skipped:
                    </p>
                    {importResult.errors.map((err, i) => (
                      <p key={i} className="text-xs text-muted-foreground">
                        Row {err.row}
                        {err.student_number
                          ? ` (${err.student_number})`
                          : ''}: {err.message}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {groups.length > 0 && students.length > 0 && (
            <form
              onSubmit={handleAssign}
              className="rounded-lg bg-card border border-border p-5 space-y-4"
            >
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <UserCheck size={15} />
                Assign to Group
              </h3>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Student *
                </label>
                <select
                  value={assignStudentId}
                  onChange={(e) => setAssignStudentId(e.target.value)}
                  className={inputClass}
                >
                  <option value="">— Select student —</option>
                  {students.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.student_number})
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Group *
                </label>
                <select
                  value={assignGroupId}
                  onChange={(e) => setAssignGroupId(e.target.value)}
                  className={inputClass}
                >
                  <option value="">— Select group —</option>
                  {groups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </div>
              {assignError && (
                <p className="text-xs text-red-400">{assignError}</p>
              )}
              <button
                type="submit"
                disabled={assigning}
                className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {assigning ? 'Assigning…' : 'Assign'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
