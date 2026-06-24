'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ChevronDown,
  FileSpreadsheet,
  FolderPlus,
  MoveRight,
  Search,
  Upload,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import { apiGetLoginUsers } from '@/lib/auth';
import {
  addCoTeacher,
  addProjectStudent,
  bulkMoveStudents,
  createProjectGroup,
  deleteProjectGroup,
  getProject,
  listCoTeachers,
  listProjectGroups,
  listProjectStudents,
  importProjectStudents,
  removeCoTeacher,
  updateModuleStudent,
  updateProjectGroup,
} from '@/lib/api/modulesApi';
import {
  ModuleDeleteConfirmDialog,
  useDeleteConfirm,
} from '@/lib/hooks/useDeleteConfirm';
import { APP_PATHS } from '@/lib/routes';
import { UI_STATUS_LABELS } from '@/lib/uiStatusLabels';
import { useModuleViewOnly } from '@/lib/hooks/useModuleViewOnly';
import ViewModeBanner from '@/components/common/ViewModeBanner';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

export default function ModuleManagePage() {
  const { moduleId } = useParams();
  const router = useRouter();
  const [moduleName, setModuleName] = useState('');
  const [moduleTeacherId, setModuleTeacherId] = useState(null);
  const [groups, setGroups] = useState([]);
  const [students, setStudents] = useState([]);
  const [studentSearch, setStudentSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [newGroupName, setNewGroupName] = useState('');
  const [groupSaving, setGroupSaving] = useState(false);
  const [groupError, setGroupError] = useState('');

  const [editingGroupId, setEditingGroupId] = useState('');
  const [editGroupName, setEditGroupName] = useState('');
  const [editGroupLabel, setEditGroupLabel] = useState('');

  const [newName, setNewName] = useState('');
  const [newStudentNumber, setNewStudentNumber] = useState('');
  const [newStudentGroupId, setNewStudentGroupId] = useState('');
  const [studentSaving, setStudentSaving] = useState(false);
  const [studentError, setStudentError] = useState('');

  const fileInputRef = useRef(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importError, setImportError] = useState('');

  const [editingStudentId, setEditingStudentId] = useState('');
  const [editName, setEditName] = useState('');
  const [editStudentNumber, setEditStudentNumber] = useState('');
  const [editStatus, setEditStatus] = useState('active');
  const [editGroupId, setEditGroupId] = useState('');
  const [editError, setEditError] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  // Co-teachers state
  const [coTeachers, setCoTeachers] = useState([]);
  const [coTeacherSaving, setCoTeacherSaving] = useState(false);
  const [coTeacherError, setCoTeacherError] = useState('');
  const [coTeacherSuccess, setCoTeacherSuccess] = useState('');
  const [removingCoTeacherId, setRemovingCoTeacherId] = useState('');

  // Co-teacher searchable dropdown state
  const [allTeachers, setAllTeachers] = useState([]);
  const [allTeachersLoading, setAllTeachersLoading] = useState(false);
  const [selectedCoTeacher, setSelectedCoTeacher] = useState(null);
  const [coTeacherSearch, setCoTeacherSearch] = useState('');
  const [coTeacherDropdownOpen, setCoTeacherDropdownOpen] = useState(false);
  const [coTeacherHighlightedIndex, setCoTeacherHighlightedIndex] = useState(0);
  const coTeacherDropdownRef = useRef(null);

  // Multi-select & bulk move state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkTargetGroupId, setBulkTargetGroupId] = useState('');
  const [bulkMoving, setBulkMoving] = useState(false);
  const [bulkError, setBulkError] = useState('');
  const [bulkSuccess, setBulkSuccess] = useState('');

  const {
    pendingItem: groupDeleteTarget,
    requestDelete: requestGroupDelete,
    cancelDelete: cancelGroupDelete,
    confirmDelete: confirmGroupDelete,
  } = useDeleteConfirm({
    onDelete: async (group) => {
      setGroupError('');
      setGroupSaving(true);
      try {
        await deleteProjectGroup(moduleId, group.id);
      } finally {
        setGroupSaving(false);
      }
    },
    onDeleted: (group) => {
      setGroups((prev) => prev.filter((g) => g.id !== group.id));
      setStudents((prev) =>
        prev.map((student) =>
          student.project_id === group.id
            ? { ...student, project_id: '' }
            : student
        )
      );
      if (newStudentGroupId === group.id) setNewStudentGroupId('');
      if (editGroupId === group.id) setEditGroupId('');
      if (bulkTargetGroupId === group.id) setBulkTargetGroupId('');
    },
    onError: (err) => {
      setGroupError(err.message);
    },
  });

  const filteredStudents = students.filter((student) => {
    const query = studentSearch.trim().toLowerCase();
    if (!query) return true;
    return (
      student.name.toLowerCase().includes(query) ||
      student.student_number.toLowerCase().includes(query)
    );
  });

  useEffect(() => {
    Promise.all([
      getProject(moduleId),
      listProjectGroups(moduleId),
      listProjectStudents(moduleId),
      listCoTeachers(moduleId).catch(() => []),
    ])
      .then(([module, groupList, studentList, coTeacherList]) => {
        setModuleName(module.name);
        setModuleTeacherId(module.teacher_id ?? null);
        setGroups(groupList);
        setStudents(studentList);
        setCoTeachers(coTeacherList);
        setLoadError('');
      })
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [moduleId]);

  const handleCreateGroup = async (e) => {
    e.preventDefault();
    if (!newGroupName.trim()) {
      setGroupError('Group name is required.');
      return;
    }

    setGroupError('');
    setGroupSaving(true);
    try {
      const created = await createProjectGroup(moduleId, {
        name: newGroupName.trim(),
      });
      setGroups((prev) => [created, ...prev]);
      setNewGroupName('');
    } catch (err) {
      setGroupError(err.message);
    } finally {
      setGroupSaving(false);
    }
  };

  const openEditGroup = (group) => {
    setEditingGroupId(group.id);
    setEditGroupName(group.name || '');
    setEditGroupLabel(group.group_name || group.name || '');
    setGroupError('');
  };

  const handleSaveGroup = async (e) => {
    e.preventDefault();
    if (!editingGroupId) return;
    if (!editGroupName.trim()) {
      setGroupError('Group name is required.');
      return;
    }

    setGroupError('');
    setGroupSaving(true);
    try {
      const updated = await updateProjectGroup(moduleId, editingGroupId, {
        name: editGroupName.trim(),
        group_name: editGroupLabel.trim() || editGroupName.trim(),
      });
      setGroups((prev) =>
        prev.map((group) =>
          group.id === editingGroupId ? { ...group, ...updated } : group
        )
      );
      setEditingGroupId('');
    } catch (err) {
      setGroupError(err.message);
    } finally {
      setGroupSaving(false);
    }
  };

  const handleDeleteGroup = (group) => {
    requestGroupDelete(group);
  };

  const handleAddStudent = async (e) => {
    e.preventDefault();
    if (!newName.trim() || !newStudentNumber.trim()) {
      setStudentError('Name and student number are required.');
      return;
    }

    setStudentError('');
    setStudentSaving(true);
    try {
      const created = await addProjectStudent(moduleId, {
        name: newName.trim(),
        student_number: newStudentNumber.trim(),
        project_id: newStudentGroupId || null,
      });
      setStudents((prev) =>
        [...prev, created].sort((a, b) => a.name.localeCompare(b.name))
      );
      setNewName('');
      setNewStudentNumber('');
    } catch (err) {
      setStudentError(err.message);
    } finally {
      setStudentSaving(false);
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    setImportError('');
    setImportResult(null);
    try {
      const result = await importProjectStudents(moduleId, file);
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
      e.target.value = '';
    }
  };

  const openEditStudent = (student) => {
    setEditingStudentId(student.id);
    setEditName(student.name);
    setEditStudentNumber(student.student_number);
    setEditStatus(student.status || 'active');
    setEditGroupId(student.project_id || '');
    setEditError('');
  };

  const handleSaveStudent = async (e) => {
    e.preventDefault();
    if (!editingStudentId) return;
    if (!editName.trim() || !editStudentNumber.trim()) {
      setEditError('Name and student number are required.');
      return;
    }

    setEditError('');
    setEditSaving(true);
    try {
      const updated = await updateModuleStudent(moduleId, editingStudentId, {
        name: editName.trim(),
        student_number: editStudentNumber.trim(),
        status: editStatus,
        project_id: editGroupId || null,
      });
      setStudents((prev) =>
        prev.map((student) =>
          student.id === editingStudentId ? { ...student, ...updated } : student
        )
      );
      setEditingStudentId('');
    } catch (err) {
      setEditError(err.message);
    } finally {
      setEditSaving(false);
    }
  };

  // ── Multi-select & bulk move helpers ─────────────────────────────────────

  const toggleSelectMode = () => {
    setSelectMode((prev) => !prev);
    setSelectedIds(new Set());
    setBulkTargetGroupId('');
    setBulkError('');
    setBulkSuccess('');
    // Close any open edit form when entering select mode
    setEditingStudentId('');
  };

  const toggleStudent = (studentId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(studentId)) {
        next.delete(studentId);
      } else {
        next.add(studentId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredStudents.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredStudents.map((s) => s.id)));
    }
  };

  const handleBulkMove = async () => {
    setBulkError('');
    setBulkSuccess('');

    if (selectedIds.size === 0) {
      setBulkError('Select at least one student to move.');
      return;
    }
    if (!bulkTargetGroupId) {
      setBulkError('Choose a destination group.');
      return;
    }

    setBulkMoving(true);
    try {
      const result = await bulkMoveStudents(
        moduleId,
        Array.from(selectedIds),
        bulkTargetGroupId
      );

      // Update the project_id of moved students in local state
      setStudents((prev) =>
        prev.map((s) =>
          selectedIds.has(s.id)
            ? { ...s, project_id: bulkTargetGroupId }
            : s
        )
      );

      const targetGroup = groups.find((g) => g.id === bulkTargetGroupId);
      const targetName = targetGroup?.name || 'the selected group';
      setBulkSuccess(
        `${result.moved_count} student${result.moved_count !== 1 ? 's' : ''} moved to "${targetName}".` +
          (result.skipped_count > 0
            ? ` ${result.skipped_count} skipped (not found in this module).`
            : '')
      );
      setSelectedIds(new Set());
      setBulkTargetGroupId('');
      setSelectMode(false);
    } catch (err) {
      setBulkError(err.message);
    } finally {
      setBulkMoving(false);
    }
  };

  // ── Co-teacher dropdown handlers ─────────────────────────────────────

  // Load all teachers once when the dropdown is first opened
  const handleOpenCoTeacherDropdown = () => {
    setCoTeacherDropdownOpen(true);
    setCoTeacherHighlightedIndex(0);
    if (allTeachers.length === 0 && !allTeachersLoading) {
      setAllTeachersLoading(true);
      apiGetLoginUsers(false)
        .then(setAllTeachers)
        .catch(() => setAllTeachers([]))
        .finally(() => setAllTeachersLoading(false));
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (
        coTeacherDropdownRef.current &&
        !coTeacherDropdownRef.current.contains(e.target)
      ) {
        setCoTeacherDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredCoTeacherOptions = allTeachers.filter((t) => {
    // Exclude already-added co-teachers and the module owner
    if (coTeachers.some((ct) => ct.id === t.id)) return false;
    const q = coTeacherSearch.trim().toLowerCase();
    if (!q) return true;
    return (
      t.name.toLowerCase().includes(q) || t.email.toLowerCase().includes(q)
    );
  });

  const handleSelectCoTeacher = (teacher) => {
    setSelectedCoTeacher(teacher);
    setCoTeacherSearch(teacher.name);
    setCoTeacherDropdownOpen(false);
    setCoTeacherError('');
    setCoTeacherSuccess('');
  };

  // ── Co-teacher handlers ───────────────────────────────────────────────

  const handleAddCoTeacher = async (e) => {
    e.preventDefault();
    if (!selectedCoTeacher) {
      setCoTeacherError('Please select a teacher from the list.');
      return;
    }
    setCoTeacherError('');
    setCoTeacherSuccess('');
    setCoTeacherSaving(true);
    try {
      const added = await addCoTeacher(moduleId, selectedCoTeacher.email);
      setCoTeachers((prev) => [...prev, added]);
      setSelectedCoTeacher(null);
      setCoTeacherSearch('');
      setCoTeacherSuccess(`${added.name} added as co-teacher.`);
    } catch (err) {
      setCoTeacherError(err.message);
    } finally {
      setCoTeacherSaving(false);
    }
  };

  const handleRemoveCoTeacher = async (teacher) => {
    setRemovingCoTeacherId(teacher.id);
    setCoTeacherError('');
    setCoTeacherSuccess('');
    try {
      await removeCoTeacher(moduleId, teacher.id);
      setCoTeachers((prev) => prev.filter((t) => t.id !== teacher.id));
      setCoTeacherSuccess(`${teacher.name} removed from co-teachers.`);
    } catch (err) {
      setCoTeacherError(err.message);
    } finally {
      setRemovingCoTeacherId('');
    }
  };

  const viewOnly = useModuleViewOnly(moduleTeacherId);

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

  return (
    <div className="space-y-6">
      {viewOnly && <ViewModeBanner />}

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {viewOnly ? 'View Roster' : 'Manage Roster'}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{moduleName}</p>
        </div>
        <button
          type="button"
          onClick={() => router.push(`${APP_PATHS.modules}/${moduleId}`)}
          className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
        >
          Back to Module
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="space-y-4 lg:col-span-2">
          <div className="rounded-lg bg-card border border-border p-5 space-y-4">
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <FolderPlus size={15} />
              Project Groups
            </h2>

            {!viewOnly && (
              <form onSubmit={handleCreateGroup} className="space-y-3">
                <input
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  placeholder="e.g. Group 2"
                  className={inputClass}
                />
                <button
                  type="submit"
                  disabled={groupSaving}
                  className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
                >
                  {groupSaving ? UI_STATUS_LABELS.saving : 'Create Group'}
                </button>
              </form>
            )}

            <div className="rounded-lg bg-secondary/20 border border-border divide-y divide-border overflow-hidden">
              <div className="px-4 py-3 text-xs font-semibold text-foreground">
                Groups ({groups.length})
              </div>
              {groups.map((group) => (
                <div key={group.id} className="px-4 py-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-foreground">
                        {group.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {group.student_count}{' '}
                        {group.student_count === 1 ? 'student' : 'students'}
                      </p>
                    </div>
                    {!viewOnly && (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => openEditGroup(group)}
                          className="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card transition-all"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteGroup(group)}
                          className="px-3 py-1.5 rounded-md border border-red-500/30 text-xs font-medium text-red-400 hover:bg-red-500/10 transition-all"
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </div>

                  {!viewOnly && editingGroupId === group.id && (
                    <form
                      onSubmit={handleSaveGroup}
                      className="rounded-md bg-card border border-border p-3 space-y-2"
                    >
                      <input
                        value={editGroupName}
                        onChange={(e) => setEditGroupName(e.target.value)}
                        placeholder="Internal group name"
                        className={inputClass}
                      />
                      <input
                        value={editGroupLabel}
                        onChange={(e) => setEditGroupLabel(e.target.value)}
                        placeholder="Display label"
                        className={inputClass}
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setEditingGroupId('')}
                          className="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={groupSaving}
                          className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
                        >
                          {groupSaving ? UI_STATUS_LABELS.saving : 'Save'}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              ))}
              {groups.length === 0 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                  No groups yet.
                </div>
              )}
            </div>

            {groupError && <p className="text-xs text-red-400">{groupError}</p>}
          </div>
        </div>

        {!viewOnly && (
          <div className="lg:col-span-1">
            <div className="rounded-lg bg-card border border-border p-5 space-y-4 mb-4">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Users size={15} />
                Add Student
              </h2>
              <form onSubmit={handleAddStudent} className="space-y-3">
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Full name"
                  className={inputClass}
                />
                <input
                  value={newStudentNumber}
                  onChange={(e) => setNewStudentNumber(e.target.value)}
                  placeholder="Student number"
                  className={`${inputClass} font-mono`}
                />
                <select
                  value={newStudentGroupId}
                  onChange={(e) => setNewStudentGroupId(e.target.value)}
                  className={inputClass}
                >
                  <option value="">Default individual group</option>
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  disabled={studentSaving}
                  className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
                >
                  {studentSaving ? UI_STATUS_LABELS.saving : 'Add Student'}
                </button>
              </form>
              {studentError && (
                <p className="text-xs text-red-400">{studentError}</p>
              )}
            </div>

            <div className="rounded-lg bg-card border border-border p-5 space-y-3">
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <FileSpreadsheet size={15} />
                Import from Excel
              </h3>
              <p className="text-xs text-muted-foreground">
                Upload an Excel (.xlsx) or CSV file with Name and Student Number
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
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-md border border-border bg-secondary text-sm font-semibold text-foreground hover:bg-secondary/70 transition-colors disabled:opacity-60"
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
                        {importResult.error_count === 1 ? 'row' : 'rows'}{' '}
                        skipped:
                      </p>
                      {importResult.errors.map((err, i) => (
                        <p key={i} className="text-xs text-muted-foreground">
                          Row {err.row}
                          {err.student_number ? ` (${err.student_number})` : ''}
                          : {err.message}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Students table ──────────────────────────────────────────────── */}
        <div className="lg:col-span-3 rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
          {/* Header row */}
          <div className="px-5 py-4 flex items-center justify-between gap-3">
            <span className="text-sm font-semibold text-foreground">
              Students ({students.length})
            </span>
            {students.length > 0 && (
              <button
                type="button"
                onClick={toggleSelectMode}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-semibold transition-colors ${
                  selectMode
                    ? 'border-primary/40 bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:text-foreground hover:bg-secondary'
                }`}
              >
                <MoveRight size={13} />
                {selectMode ? 'Cancel selection' : 'Move students'}
              </button>
            )}
          </div>

          {/* Bulk-move toolbar */}
          {selectMode && students.length > 0 && (
            <div className="px-5 py-3 bg-primary/5 border-b border-border space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-medium text-foreground">
                  {selectedIds.size === 0
                    ? 'Select students below to move them'
                    : `${selectedIds.size} student${selectedIds.size !== 1 ? 's' : ''} selected`}
                </p>
                <button
                  type="button"
                  onClick={toggleSelectAll}
                  className="text-xs text-primary hover:underline shrink-0"
                >
                  {selectedIds.size === filteredStudents.length
                    ? 'Deselect all'
                    : 'Select all'}
                </button>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={bulkTargetGroupId}
                  onChange={(e) => setBulkTargetGroupId(e.target.value)}
                  className={`${inputClass} flex-1`}
                  disabled={bulkMoving}
                >
                  <option value="">— Choose destination group —</option>
                  {groups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleBulkMove}
                  disabled={
                    bulkMoving || selectedIds.size === 0 || !bulkTargetGroupId
                  }
                  className="shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {bulkMoving ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      {UI_STATUS_LABELS.saving}
                    </>
                  ) : (
                    <>
                      <MoveRight size={14} />
                      Move
                    </>
                  )}
                </button>
              </div>
              {bulkError && (
                <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                  {bulkError}
                </p>
              )}
            </div>
          )}

          {/* Success banner (shown after selectMode closes) */}
          {!selectMode && bulkSuccess && (
            <div className="px-5 py-3 bg-emerald-500/10 border-b border-emerald-500/20">
              <p className="text-xs text-emerald-400">{bulkSuccess}</p>
            </div>
          )}

          {/* Search bar */}
          <div className="px-5 py-3 bg-secondary/20">
            <input
              value={studentSearch}
              onChange={(e) => setStudentSearch(e.target.value)}
              placeholder="Search by name or student number"
              className={inputClass}
            />
          </div>

          {/* Student cards */}
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {filteredStudents.map((student) => {
              const isSelected = selectedIds.has(student.id);
              return (
                <div
                  key={student.id}
                  className={`rounded-md border p-3 space-y-3 transition-colors ${
                    selectMode
                      ? isSelected
                        ? 'border-primary/40 bg-primary/10 cursor-pointer'
                        : 'border-border bg-secondary/20 cursor-pointer hover:bg-secondary/40'
                      : 'border-border bg-secondary/20'
                  }`}
                  onClick={() => {
                    if (selectMode) toggleStudent(student.id);
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    {/* Checkbox (select mode only) */}
                    {selectMode && (
                      <div
                        className={`mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 transition-colors ${
                          isSelected
                            ? 'bg-primary border-primary'
                            : 'border-border bg-transparent'
                        }`}
                      >
                        {isSelected && (
                          <svg
                            className="w-2.5 h-2.5 text-primary-foreground"
                            fill="none"
                            viewBox="0 0 12 12"
                          >
                            <path
                              d="M2 6l3 3 5-5"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        )}
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-foreground">
                        {student.name}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono">
                        {student.student_number}
                      </p>
                      {/* Group badge */}
                      {student.project_id && (
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          {groups.find((g) => g.id === student.project_id)
                            ?.name || '—'}
                        </p>
                      )}
                      <span
                        className={`mt-1 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          student.status === 'inactive'
                            ? 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20'
                        }`}
                      >
                        {student.status === 'inactive' ? 'Dropped out' : 'Active'}
                      </span>
                    </div>
                    <div className="w-14 text-right shrink-0">
                      <p className="text-[11px] text-muted-foreground">Grade</p>
                      <p className="text-sm font-semibold text-foreground">
                        {student.grade || '—'}
                      </p>
                    </div>
                  </div>

                  {/* Edit button — hidden in select mode */}
                  {!selectMode && !viewOnly && (
                    <button
                      type="button"
                      onClick={() => openEditStudent(student)}
                      className="w-full px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
                    >
                      Edit
                    </button>
                  )}

                  {!selectMode && !viewOnly && editingStudentId === student.id && (
                    <form
                      onSubmit={handleSaveStudent}
                      className="rounded-md bg-card border border-border p-3 space-y-2"
                    >
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="Student name"
                        className={inputClass}
                      />
                      <input
                        value={editStudentNumber}
                        onChange={(e) => setEditStudentNumber(e.target.value)}
                        placeholder="Student number"
                        className={`${inputClass} font-mono`}
                      />
                      <select
                        value={editGroupId}
                        onChange={(e) => setEditGroupId(e.target.value)}
                        className={inputClass}
                      >
                        <option value="">Default individual group</option>
                        {groups.map((group) => (
                          <option key={group.id} value={group.id}>
                            {group.name}
                          </option>
                        ))}
                      </select>
                      <select
                        value={editStatus}
                        onChange={(e) => setEditStatus(e.target.value)}
                        className={inputClass}
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Dropped out</option>
                      </select>
                      {editError && (
                        <p className="text-xs text-red-400">{editError}</p>
                      )}
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setEditingStudentId('')}
                          className="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-card transition-all"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          disabled={editSaving}
                          className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60"
                        >
                          {editSaving ? UI_STATUS_LABELS.saving : 'Save'}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              );
            })}
          </div>
          {filteredStudents.length === 0 && (
            <div className="px-5 pb-6 text-center text-sm text-muted-foreground">
              No students match your search.
            </div>
          )}
        </div>
      </div>

      {/* ── Co-teachers section ─────────────────────────────────────────── */}
      <div className="rounded-lg bg-card border border-border p-5 space-y-4">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <UserPlus size={15} />
          Co-teachers
        </h2>
        <p className="text-xs text-muted-foreground">
          Co-teachers can view and manage this module. Only the module owner can
          add or remove co-teachers.
        </p>

        {/* Add co-teacher form — searchable dropdown */}
        <form onSubmit={handleAddCoTeacher} className="flex items-center gap-2">
          <div className="relative flex-1" ref={coTeacherDropdownRef}>
            {/* Trigger button */}
            <button
              type="button"
              onClick={handleOpenCoTeacherDropdown}
              disabled={coTeacherSaving}
              className={`w-full bg-secondary border rounded-md px-3 py-2 text-sm text-left flex items-center justify-between transition-all focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed ${
                selectedCoTeacher
                  ? 'border-border text-foreground'
                  : 'border-border text-muted-foreground'
              }`}
            >
              <span className="truncate">
                {selectedCoTeacher
                  ? selectedCoTeacher.name
                  : allTeachersLoading
                    ? 'Loading…'
                    : 'Select teacher…'}
              </span>
              <ChevronDown
                size={14}
                className={`shrink-0 ml-2 text-muted-foreground transition-transform ${coTeacherDropdownOpen ? 'rotate-180' : ''}`}
              />
            </button>

            {/* Dropdown panel */}
            {coTeacherDropdownOpen && (
              <div className="absolute z-20 w-full mt-1 bg-background border border-border rounded-md shadow-lg overflow-hidden">
                {/* Search input */}
                <div className="p-2 border-b border-border">
                  <div className="flex items-center gap-2 bg-secondary rounded-md px-2.5 py-1.5">
                    <Search size={13} className="text-muted-foreground shrink-0" />
                    <input
                      autoFocus
                      type="text"
                      value={coTeacherSearch}
                      onChange={(e) => {
                        setCoTeacherSearch(e.target.value);
                        setCoTeacherHighlightedIndex(0);
                        if (
                          selectedCoTeacher &&
                          e.target.value !== selectedCoTeacher.name
                        ) {
                          setSelectedCoTeacher(null);
                        }
                      }}
                      onKeyDown={(e) => {
                        if (
                          e.key === 'Enter' &&
                          filteredCoTeacherOptions.length > 0
                        ) {
                          e.preventDefault();
                          handleSelectCoTeacher(
                            filteredCoTeacherOptions[coTeacherHighlightedIndex]
                          );
                        } else if (e.key === 'ArrowDown') {
                          setCoTeacherHighlightedIndex((i) =>
                            Math.min(i + 1, filteredCoTeacherOptions.length - 1)
                          );
                        } else if (e.key === 'ArrowUp') {
                          setCoTeacherHighlightedIndex((i) =>
                            Math.max(i - 1, 0)
                          );
                        } else if (e.key === 'Escape') {
                          setCoTeacherDropdownOpen(false);
                        }
                      }}
                      placeholder="Search by name or email…"
                      className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                    />
                  </div>
                </div>

                {/* Options list */}
                <ul className="max-h-48 overflow-y-auto py-1">
                  {allTeachersLoading ? (
                    <li className="px-3 py-2 text-sm text-muted-foreground">
                      Loading teachers…
                    </li>
                  ) : filteredCoTeacherOptions.length === 0 ? (
                    <li className="px-3 py-2 text-sm text-muted-foreground">
                      No teachers found
                    </li>
                  ) : (
                    filteredCoTeacherOptions.map((t, index) => (
                      <li key={t.id}>
                        <button
                          type="button"
                          onClick={() => handleSelectCoTeacher(t)}
                          className={`w-full text-left px-3 py-2 text-sm hover:bg-secondary transition-colors ${
                            index === coTeacherHighlightedIndex
                              ? 'bg-secondary text-foreground font-medium'
                              : 'text-foreground'
                          }`}
                        >
                          <span className="block">{t.name}</span>
                          <span className="block text-xs text-muted-foreground">
                            {t.email}
                          </span>
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={coTeacherSaving || !selectedCoTeacher}
            className="shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {coTeacherSaving ? (
              <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <UserPlus size={14} />
            )}
            Add
          </button>
        </form>

        {coTeacherError && (
          <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
            {coTeacherError}
          </p>
        )}
        {coTeacherSuccess && (
          <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
            {coTeacherSuccess}
          </p>
        )}

        {/* Co-teacher list */}
        {coTeachers.length > 0 ? (
          <div className="rounded-lg bg-secondary/20 border border-border divide-y divide-border overflow-hidden">
            <div className="px-4 py-3 text-xs font-semibold text-foreground">
              Co-teachers ({coTeachers.length})
            </div>
            {coTeachers.map((teacher) => (
              <div
                key={teacher.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground truncate">
                    {teacher.name}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {teacher.email}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveCoTeacher(teacher)}
                  disabled={removingCoTeacherId === teacher.id}
                  className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-red-500/30 text-xs font-medium text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Remove co-teacher"
                >
                  {removingCoTeacherId === teacher.id ? (
                    <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <X size={12} />
                  )}
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            No co-teachers added yet.
          </p>
        )}
      </div>

      <ModuleDeleteConfirmDialog
        open={Boolean(groupDeleteTarget)}
        title="Delete Group"
        label={groupDeleteTarget?.name}
        message={
          <>
            Delete{' '}
            <span className="font-semibold text-foreground">
              {groupDeleteTarget?.name}
            </span>
            ? Students in this group will be moved to the default group.
          </>
        }
        warningItems={[
          'Students in this group will be moved to the default group.',
        ]}
        confirmLabel="Delete group"
        loading={groupSaving}
        onConfirm={confirmGroupDelete}
        onCancel={cancelGroupDelete}
      />
    </div>
  );
}
