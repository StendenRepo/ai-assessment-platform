'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { FileSpreadsheet, FolderPlus, Upload, Users } from 'lucide-react';
import {
  addProjectStudent,
  createProjectGroup,
  deleteProjectGroup,
  getProject,
  listProjectGroups,
  listProjectStudents,
  importProjectStudents,
  updateModuleStudent,
  updateProjectGroup,
} from '@/lib/api/modulesApi';
import { APP_PATHS } from '@/lib/routes';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

export default function ModuleManagePage() {
  const { moduleId } = useParams();
  const router = useRouter();

  const [moduleName, setModuleName] = useState('');
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
    ])
      .then(([module, groupList, studentList]) => {
        setModuleName(module.name);
        setGroups(groupList);
        setStudents(studentList);
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

  const handleDeleteGroup = async (group) => {
    if (
      !confirm(
        `Delete ${group.name}? Students in this group will be moved to the default group.`
      )
    ) {
      return;
    }

    setGroupError('');
    setGroupSaving(true);
    try {
      await deleteProjectGroup(moduleId, group.id);
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
    } catch (err) {
      setGroupError(err.message);
    } finally {
      setGroupSaving(false);
    }
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
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Manage Roster</h1>
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
                {groupSaving ? 'Saving…' : 'Create Group'}
              </button>
            </form>

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
                  </div>

                  {editingGroupId === group.id && (
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
                          {groupSaving ? 'Saving…' : 'Save'}
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
                {studentSaving ? 'Saving…' : 'Add Student'}
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
        </div>

        <div className="lg:col-span-3 rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
          <div className="px-5 py-4 text-sm font-semibold text-foreground">
            Students ({students.length})
          </div>
          <div className="px-5 py-3 border-t border-border/60 bg-secondary/20">
            <input
              value={studentSearch}
              onChange={(e) => setStudentSearch(e.target.value)}
              placeholder="Search by name or student number"
              className={inputClass}
            />
          </div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {filteredStudents.map((student) => (
              <div
                key={student.id}
                className="rounded-md border border-border bg-secondary/20 p-3 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground">
                      {student.name}
                    </p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {student.student_number}
                    </p>
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
                <button
                  type="button"
                  onClick={() => openEditStudent(student)}
                  className="w-full px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
                >
                  Edit
                </button>

                {editingStudentId === student.id && (
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
                        {editSaving ? 'Saving…' : 'Save'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            ))}
          </div>
          {filteredStudents.length === 0 && (
            <div className="px-5 pb-6 text-center text-sm text-muted-foreground">
              No students match your search.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
