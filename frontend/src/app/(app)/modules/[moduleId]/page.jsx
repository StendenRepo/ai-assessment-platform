'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  BookOpen,
  Download,
  FileText,
  FolderPlus,
  Github,
  ScanSearch,
  Search,
  Users,
} from 'lucide-react';
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog';
import EvidencePreviewDialog from '@/components/evidence/EvidencePreviewDialog';
import ModuleFileCard from '@/components/modules/ModuleFileCard';
import ViewModeBanner from '@/components/common/ViewModeBanner';
import { useDeleteConfirm } from '@/lib/hooks/useDeleteConfirm';
import { useDocumentPreview } from '@/lib/hooks/useDocumentPreview';
import { useModuleViewOnly } from '@/lib/hooks/useModuleViewOnly';
import {
  getProject,
  listProjectGroups,
  listProjectStudents,
  uploadRubric,
  deleteRubric,
  uploadModuleBook,
  deleteModuleBook,
  exportGradesExcel,
  getRubricFileBlob,
  getRubricContent,
  getModuleBookFileBlob,
  getModuleBookContent,
} from '@/lib/api/modulesApi';
import { APP_PATHS } from '@/lib/routes';

export default function ModulePage() {
  const { moduleId } = useParams();
  const router = useRouter();
  const [project, setProject] = useState(null);
  const [students, setStudents] = useState([]);
  const [studentSearch, setStudentSearch] = useState('');
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const rubricInputRef = useRef(null);
  const [uploadingRubric, setUploadingRubric] = useState(false);
  const [deletingRubric, setDeletingRubric] = useState(false);
  const [rubricError, setRubricError] = useState('');
  const [pendingRubricReplace, setPendingRubricReplace] = useState(null);

  const moduleBookInputRef = useRef(null);
  const [uploadingModuleBook, setUploadingModuleBook] = useState(false);
  const [deletingModuleBook, setDeletingModuleBook] = useState(false);
  const [moduleBookError, setModuleBookError] = useState('');
  const [pendingModuleBookReplace, setPendingModuleBookReplace] =
    useState(null);

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  const docPreview = useDocumentPreview();

  const {
    pendingItem: rubricDeleteTarget,
    requestDelete: requestRubricDelete,
    cancelDelete: cancelRubricDelete,
    confirmDelete: confirmRubricDelete,
  } = useDeleteConfirm({
    onDelete: async () => {
      setRubricError('');
      setDeletingRubric(true);
      try {
        await deleteRubric(moduleId);
      } finally {
        setDeletingRubric(false);
      }
    },
    onDeleted: () => {
      setProject((prev) => ({ ...prev, rubric_file: null }));
    },
    onError: (err) => {
      setRubricError(err.message);
    },
  });

  const {
    pendingItem: moduleBookDeleteTarget,
    requestDelete: requestModuleBookDelete,
    cancelDelete: cancelModuleBookDelete,
    confirmDelete: confirmModuleBookDelete,
  } = useDeleteConfirm({
    onDelete: async () => {
      setModuleBookError('');
      setDeletingModuleBook(true);
      try {
        await deleteModuleBook(moduleId);
      } finally {
        setDeletingModuleBook(false);
      }
    },
    onDeleted: () => {
      setProject((prev) => ({ ...prev, module_book_file: null }));
    },
    onError: (err) => {
      setModuleBookError(err.message);
    },
  });

  const groupProgress = useMemo(() => {
    return students.reduce((summary, student) => {
      const current = summary[student.project_id] ?? {
        total: 0,
        completed: 0,
        inProgress: 0,
        notStarted: 0,
      };
      current.total += 1;
      if (student.assessment_status === 'completed') current.completed += 1;
      else if (student.assessment_status === 'in-progress')
        current.inProgress += 1;
      else current.notStarted += 1;
      summary[student.project_id] = current;
      return summary;
    }, {});
  }, [students]);

  const filteredStudents = useMemo(() => {
    const query = studentSearch.trim().toLowerCase();
    if (!query) return students;
    return students.filter(
      (student) =>
        student.name.toLowerCase().includes(query) ||
        student.student_number.toLowerCase().includes(query)
    );
  }, [students, studentSearch]);

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

  // ── Rubric upload ─────────────────────────────────────────────────────

  const performRubricUpload = async (file) => {
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

  const handleRubricFile = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'xlsx') {
      setRubricError(
        `Only PDF and Excel files are allowed. "${file.name}" is not supported.`
      );
      if (rubricInputRef.current) rubricInputRef.current.value = '';
      return;
    }
    const existing = project?.rubric_file;
    if (existing) {
      setPendingRubricReplace({
        oldName: existing.file_name || 'rubric',
        newName: file.name,
        file,
      });
      if (rubricInputRef.current) rubricInputRef.current.value = '';
      return;
    }
    await performRubricUpload(file);
  };

  const handleRubricDelete = () => {
    requestRubricDelete({ label: project?.rubric_file?.file_name || 'rubric' });
  };

  const handleConfirmRubricReplace = async () => {
    if (!pendingRubricReplace?.file) return;
    const nextFile = pendingRubricReplace.file;
    setPendingRubricReplace(null);
    await performRubricUpload(nextFile);
  };

  // ── Module book upload ────────────────────────────────────────────────

  const performModuleBookUpload = async (file) => {
    setModuleBookError('');
    setUploadingModuleBook(true);
    try {
      const updated = await uploadModuleBook(moduleId, file);
      setProject((prev) => ({
        ...prev,
        module_book_file: updated.module_book_file,
      }));
    } catch (err) {
      setModuleBookError(err.message);
    } finally {
      setUploadingModuleBook(false);
      if (moduleBookInputRef.current) moduleBookInputRef.current.value = '';
    }
  };

  const handleModuleBookFile = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'docx') {
      setModuleBookError(
        `Only PDF and Word (.docx) files are allowed. "${file.name}" is not supported.`
      );
      if (moduleBookInputRef.current) moduleBookInputRef.current.value = '';
      return;
    }
    const existing = project?.module_book_file;
    if (existing) {
      setPendingModuleBookReplace({
        oldName: existing.file_name || 'module book',
        newName: file.name,
        file,
      });
      if (moduleBookInputRef.current) moduleBookInputRef.current.value = '';
      return;
    }
    await performModuleBookUpload(file);
  };

  const handleModuleBookDelete = () => {
    requestModuleBookDelete({
      label: project?.module_book_file?.file_name || 'module book',
    });
  };

  const handleConfirmModuleBookReplace = async () => {
    if (!pendingModuleBookReplace?.file) return;
    const nextFile = pendingModuleBookReplace.file;
    setPendingModuleBookReplace(null);
    await performModuleBookUpload(nextFile);
  };

  // ── Grade export ──────────────────────────────────────────────────────

  const viewOnly = useModuleViewOnly(project?.teacher_id);

  const handleExportGrades = async () => {
    setExportError('');
    setExporting(true);
    try {
      const { blob, filename } = await exportGradesExcel(
        moduleId,
        project?.name || ''
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message);
    } finally {
      setExporting(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────

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
  const moduleBook = project?.module_book_file;

  const rubricDescriptor = rubric && {
    file_name: rubric.file_name || 'rubric',
    file_type: rubric.file_type,
    fetchBlob: () => getRubricFileBlob(moduleId),
    fetchContent: () => getRubricContent(moduleId),
    supportsAltText: false,
  };
  const moduleBookDescriptor = moduleBook && {
    file_name: moduleBook.file_name || 'module book',
    file_type: moduleBook.file_type,
    fetchBlob: () => getModuleBookFileBlob(moduleId),
    fetchContent: () => getModuleBookContent(moduleId),
    supportsAltText: false,
  };

  return (
    <div className="space-y-6">
      {viewOnly && <ViewModeBanner />}

      <div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              {project?.name}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {viewOnly
                ? 'Viewing module in read-only mode'
                : 'Manage the students in this module to set up the assessment'}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => router.push(APP_PATHS.moduleOverlaps(moduleId))}
              className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-all"
            >
              <ScanSearch size={14} />
              Review overlaps
            </button>
            <button
              type="button"
              onClick={handleExportGrades}
              disabled={exporting}
              className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Download size={14} />
              {exporting ? 'Exporting…' : 'Export Grades'}
            </button>
            {!viewOnly && (
              <button
                type="button"
                onClick={() => router.push(APP_PATHS.moduleManage(moduleId))}
                className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                Manage Groups & Students
              </button>
            )}
          </div>
        </div>
        {exportError && (
          <p className="mt-2 text-xs text-red-400">{exportError}</p>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* ── Left: groups + students ──────────────────────────────────── */}
        <div className="col-span-2 space-y-6">
          {/* Groups */}
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
                  Use{' '}
                  <button
                    type="button"
                    onClick={() =>
                      router.push(APP_PATHS.moduleManage(moduleId))
                    }
                    className="text-primary hover:underline"
                  >
                    Manage Groups &amp; Students
                  </button>{' '}
                  to create project groups.
                </p>
              </div>
            ) : (
              <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
                {groups.map((group) => {
                  const progress = groupProgress[group.id] ?? {
                    total: 0,
                    completed: 0,
                    inProgress: 0,
                    notStarted: 0,
                  };
                  const progressPercent =
                    progress.total > 0
                      ? Math.round((progress.completed / progress.total) * 100)
                      : 0;

                  return (
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
                      <div className="flex-1 min-w-0 space-y-3">
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
                          {group.github_repo_url && (
                            <span className="flex items-center gap-1.5 leading-none truncate">
                              <Github size={13} />
                              Repo linked
                            </span>
                          )}
                        </div>
                        <div className="space-y-1.5 pr-3">
                          <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span className="font-medium text-foreground/80">
                              Assessment progress
                            </span>
                            <span className="font-semibold text-foreground">
                              {progress.completed} completed
                            </span>
                          </div>
                          <div className="h-2.5 rounded-full bg-secondary overflow-hidden">
                            <div
                              className="h-full rounded-full bg-primary transition-all"
                              style={{ width: `${progressPercent}%` }}
                            />
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span className="font-medium">
                              {progressPercent}% complete
                            </span>
                            {progress.inProgress > 0 && (
                              <span>{progress.inProgress} in progress</span>
                            )}
                            {progress.notStarted > 0 && (
                              <span>{progress.notStarted} not started</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Students */}
          <div className="space-y-3">
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
              <Users size={16} />
              Students ({students.length})
            </h2>

            <div className="rounded-lg bg-card border border-border px-4 py-3 flex items-center gap-3">
              <Search size={15} className="text-muted-foreground shrink-0" />
              <input
                type="text"
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                placeholder="Search students by name or number"
                className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {filteredStudents.length} shown
              </span>
            </div>

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
                  Use{' '}
                  <button
                    type="button"
                    onClick={() =>
                      router.push(APP_PATHS.moduleManage(moduleId))
                    }
                    className="text-primary hover:underline"
                  >
                    Manage Groups &amp; Students
                  </button>{' '}
                  to add students.
                </p>
              </div>
            ) : filteredStudents.length === 0 ? (
              <div className="rounded-lg bg-card border border-border p-10 text-center">
                <Search
                  size={28}
                  className="mx-auto text-muted-foreground mb-3 opacity-50"
                />
                <p className="text-sm font-medium text-foreground">
                  No students found
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Try a different name or student number.
                </p>
              </div>
            ) : (
              <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
                {filteredStudents.map((student) => (
                  <div
                    key={student.id}
                    onClick={() =>
                      router.push(
                        `${APP_PATHS.modules}/${moduleId}/groups/${student.project_id}/students/${student.id}?from=module`
                      )
                    }
                    className="px-5 py-4 flex items-center gap-4 hover:bg-secondary/50 cursor-pointer transition-colors"
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
                      {student.github_repo_url && (
                        <a
                          href={student.github_repo_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <Github size={12} />
                          GitHub Repo
                        </a>
                      )}
                    </div>
                    <div className="w-16 text-right shrink-0">
                      <div className="text-xs text-muted-foreground">Grade</div>
                      <div className="text-sm font-semibold text-foreground">
                        {student.grade || '—'}
                      </div>
                    </div>
                    <span
                      className={`inline-flex items-center justify-center w-24 rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${
                        student.status === 'inactive'
                          ? 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20'
                      }`}
                    >
                      {student.status === 'inactive' ? 'Dropped out' : 'Active'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: rubric + module book ──────────────────────────────── */}
        <div className="col-span-1 space-y-6">
          <ModuleFileCard
            title="Rubric File"
            icon={FileText}
            description={
              <>
                Attach a rubric so the AI knows the grading criteria for this
                module. Only{' '}
                <span className="font-semibold text-foreground">PDF</span> or{' '}
                <span className="font-semibold text-foreground">Excel</span>{' '}
                (.xlsx) files are accepted.
              </>
            }
            accept=".pdf,.xlsx"
            file={rubric}
            fallbackName="rubric"
            descriptor={rubricDescriptor}
            inputRef={rubricInputRef}
            uploading={uploadingRubric}
            deleting={deletingRubric}
            error={rubricError}
            onFileChange={handleRubricFile}
            onDelete={handleRubricDelete}
            docPreview={docPreview}
            readOnly={viewOnly}
          />

          <ModuleFileCard
            title="Module Book"
            icon={BookOpen}
            description={
              <>
                Upload the module book so the AI understands the course content.
                Only <span className="font-semibold text-foreground">PDF</span>{' '}
                or <span className="font-semibold text-foreground">Word</span>{' '}
                (.docx) files are accepted.
              </>
            }
            accept=".pdf,.docx"
            file={moduleBook}
            fallbackName="module book"
            descriptor={moduleBookDescriptor}
            inputRef={moduleBookInputRef}
            uploading={uploadingModuleBook}
            deleting={deletingModuleBook}
            error={moduleBookError}
            onFileChange={handleModuleBookFile}
            onDelete={handleModuleBookDelete}
            docPreview={docPreview}
            readOnly={viewOnly}
          />
        </div>
      </div>

      {/* ── Dialogs ──────────────────────────────────────────────────────── */}
      <DeleteConfirmDialog
        open={Boolean(rubricDeleteTarget)}
        title="Remove Rubric"
        label={rubricDeleteTarget?.label}
        message={
          <>
            Remove the rubric{' '}
            <span className="font-semibold text-foreground">
              {rubricDeleteTarget?.label}
            </span>{' '}
            from this module?
          </>
        }
        loading={deletingRubric}
        confirmLabel="Remove"
        onConfirm={confirmRubricDelete}
        onCancel={cancelRubricDelete}
      />

      <DeleteConfirmDialog
        open={Boolean(pendingRubricReplace)}
        title="Replace Rubric"
        confirmLabel="Replace"
        message={
          <>
            Are you sure you want to replace{' '}
            <span className="font-semibold text-foreground">
              {pendingRubricReplace?.oldName}
            </span>{' '}
            with{' '}
            <span className="font-semibold text-foreground">
              {pendingRubricReplace?.newName}
            </span>
            ?
          </>
        }
        onConfirm={handleConfirmRubricReplace}
        onCancel={() => setPendingRubricReplace(null)}
      />

      <DeleteConfirmDialog
        open={Boolean(moduleBookDeleteTarget)}
        title="Remove Module Book"
        label={moduleBookDeleteTarget?.label}
        message={
          <>
            Remove the module book{' '}
            <span className="font-semibold text-foreground">
              {moduleBookDeleteTarget?.label}
            </span>{' '}
            from this module?
          </>
        }
        loading={deletingModuleBook}
        confirmLabel="Remove"
        onConfirm={confirmModuleBookDelete}
        onCancel={cancelModuleBookDelete}
      />

      <DeleteConfirmDialog
        open={Boolean(pendingModuleBookReplace)}
        title="Replace Module Book"
        confirmLabel="Replace"
        message={
          <>
            Are you sure you want to replace{' '}
            <span className="font-semibold text-foreground">
              {pendingModuleBookReplace?.oldName}
            </span>{' '}
            with{' '}
            <span className="font-semibold text-foreground">
              {pendingModuleBookReplace?.newName}
            </span>
            ?
          </>
        }
        onConfirm={handleConfirmModuleBookReplace}
        onCancel={() => setPendingModuleBookReplace(null)}
      />

      {(docPreview.previewDoc || docPreview.previewLoading) && (
        <EvidencePreviewDialog
          evidence={docPreview.previewDoc}
          previewKind={docPreview.activePreviewKind}
          basePreviewKind={docPreview.basePreviewKind}
          previewUrl={docPreview.previewUrl}
          previewContent={docPreview.previewContent}
          loading={docPreview.previewLoading}
          showImageExtractedText={docPreview.showImageExtractedText}
          onToggleImageExtractedText={docPreview.toggleImageExtractedText}
          onClose={docPreview.closePreview}
        />
      )}
    </div>
  );
}
