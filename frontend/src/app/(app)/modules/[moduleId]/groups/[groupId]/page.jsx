'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  Clock,
  Github,
  GitBranch,
  ScanSearch,
  Users,
} from 'lucide-react';
import {
  getProject,
  listProjectGroups,
  listProjectStudents,
  updateProjectGroup,
  verifyGithubRepo,
} from '@/lib/api/modulesApi';
import ProjectEvidencePanel from '@/components/evidence/ProjectEvidencePanel';
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog';
import { APP_PATHS } from '@/lib/routes';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

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

function formatAsDdMmYyyy(value) {
  if (!value) return '—';
  const parts = String(value).split('-');
  if (parts.length !== 3) return value;
  const [year, month, day] = parts;
  if (!year || !month || !day) return value;
  return `${day}-${month}-${year}`;
}

export default function GroupDetailPage() {
  const { moduleId, groupId } = useParams();
  const router = useRouter();

  const [module, setModule] = useState(null);
  const [group, setGroup] = useState(null);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [repoBranch, setRepoBranch] = useState('');
  const [branches, setBranches] = useState([]);
  const [verified, setVerified] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [repoSaving, setRepoSaving] = useState(false);
  const [repoError, setRepoError] = useState('');
  const [repoSuccess, setRepoSuccess] = useState('');
  const [editing, setEditing] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);

  useEffect(() => {
    Promise.all([
      getProject(moduleId),
      listProjectGroups(moduleId),
      listProjectStudents(moduleId),
    ])
      .then(([mod, groups, allStudents]) => {
        setModule(mod);
        const found = groups.find((g) => g.id === groupId);
        if (!found) {
          setLoadError('Group not found.');
          return;
        }
        setGroup(found);
        setRepoUrl(found.github_repo_url || '');
        setRepoBranch(found.github_branch || '');
        // If the group already has a saved repo + branch, show in "verified" state
        // so the user immediately sees the branch dropdown pre-populated.
        if (found.github_repo_url) {
          setVerified(true);
          setBranches(found.github_branch ? [found.github_branch] : []);
        }
        setEditing(!found.github_repo_url);
        setStudents(allStudents.filter((s) => s.project_id === groupId));
      })
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [moduleId, groupId]);

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
        <p className="text-sm font-medium text-red-400">{loadError}</p>
      </div>
    );
  }

  const handleVerifyRepo = async () => {
    setRepoError('');
    setRepoSuccess('');
    setVerified(false);
    setBranches([]);
    setRepoBranch('');
    if (!repoUrl.trim()) {
      setRepoError('Enter a GitHub repository URL first.');
      return;
    }
    setVerifying(true);
    try {
      const result = await verifyGithubRepo(repoUrl.trim());
      setBranches(result.branches);
      setRepoBranch(result.default_branch);
      setVerified(true);
      setRepoSuccess(
        `Repository verified. ${result.branches.length} branch${result.branches.length !== 1 ? 'es' : ''} found.`
      );
    } catch (err) {
      setRepoError(err.message);
    } finally {
      setVerifying(false);
    }
  };

  const handleSaveGroupRepo = async (e) => {
    e.preventDefault();
    setRepoError('');
    setRepoSuccess('');
    if (!verified) {
      setRepoError('Please verify the repository before saving.');
      return;
    }
    setRepoSaving(true);
    try {
      const updated = await updateProjectGroup(moduleId, groupId, {
        github_repo_url: repoUrl.trim() || null,
        github_branch: repoBranch || null,
      });
      setGroup((prev) => ({
        ...prev,
        github_repo_url: updated.github_repo_url,
        github_branch: updated.github_branch,
      }));
      setStudents((prev) =>
        prev.map((student) => ({
          ...student,
          github_repo_url: updated.github_repo_url || null,
          github_branch: updated.github_branch || null,
        }))
      );
      setRepoUrl(updated.github_repo_url || '');
      setRepoBranch(updated.github_branch || '');
      setEditing(false);
      setRepoSuccess(
        'Repository and branch saved and synced to all students in this group.'
      );
    } catch (err) {
      setRepoError(err.message);
    } finally {
      setRepoSaving(false);
    }
  };

  const handleRemoveGroupRepo = async () => {
    setRepoError('');
    setRepoSuccess('');
    setRepoSaving(true);
    try {
      await updateProjectGroup(moduleId, groupId, {
        github_repo_url: null,
        github_branch: null,
      });
      setGroup((prev) => ({
        ...prev,
        github_repo_url: null,
        github_branch: null,
      }));
      setStudents((prev) =>
        prev.map((student) => ({
          ...student,
          github_repo_url: null,
          github_branch: null,
        }))
      );
      setRepoUrl('');
      setRepoBranch('');
      setBranches([]);
      setVerified(false);
      setEditing(true);
      setRepoSuccess(
        'Repository removed from this group and all its students.'
      );
    } catch (err) {
      setRepoError(err.message);
    } finally {
      setRepoSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{group.name}</h1>
          <p className="text-sm text-muted-foreground mt-1">{module.name}</p>
        </div>
        <Link
          href={`${APP_PATHS.moduleOverlaps(moduleId)}?group_id=${groupId}`}
          className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary shrink-0"
        >
          <ScanSearch size={14} />
          Group overlaps
        </Link>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 space-y-6">
          <div className="rounded-lg bg-card border border-border">
            <div className="grid grid-cols-3 divide-x divide-border">
              {[
                { label: 'Module', value: module.name },
                { label: 'Academic Year', value: module.academic_year || '—' },
                { label: 'Deadline', value: formatAsDdMmYyyy(module.deadline) },
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

          <ProjectEvidencePanel
            projectId={group.id}
            title="Shared Project Evidence"
          />

          <div>
            <h2 className="text-base font-semibold text-foreground flex items-center gap-2 mb-3">
              <Users size={16} />
              Students ({students.length})
            </h2>

            {students.length === 0 ? (
              <div className="rounded-lg bg-card border border-border p-12 text-center">
                <Users
                  size={28}
                  className="mx-auto text-muted-foreground mb-3 opacity-50"
                />
                <p className="text-sm font-medium text-foreground">
                  No students in this group
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Assign students to this group from the module page.
                </p>
              </div>
            ) : (
              <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
                {students.map((student) => {
                  const statusCfg =
                    assessmentStatusConfig[student.assessment_status] ??
                    assessmentStatusConfig['not-started'];
                  const StatusIcon = statusCfg.icon;
                  return (
                    <div
                      key={student.id}
                      onClick={() =>
                        router.push(
                          `${APP_PATHS.modules}/${moduleId}/groups/${groupId}/students/${student.id}`
                        )
                      }
                      className="flex items-center gap-4 px-5 py-4 hover:bg-secondary/50 cursor-pointer transition-colors group"
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
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ${statusCfg.classes}`}
                      >
                        <StatusIcon size={11} />
                        {statusCfg.label}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(
                            `${APP_PATHS.modules}/${moduleId}/groups/${groupId}/students/${student.id}`
                          );
                        }}
                        className="shrink-0 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors cursor-pointer"
                      >
                        Assess
                      </button>
                      <ArrowRight
                        size={14}
                        className="text-muted-foreground shrink-0"
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="xl:col-span-1">
          <div className="sticky top-4">
            {!editing && group.github_repo_url ? (
              <div className="rounded-lg bg-card border border-border p-5 space-y-4">
                <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                  <Github size={16} />
                  Group GitHub Repo
                </h2>
                <div className="rounded-lg bg-secondary/50 border border-border p-3 space-y-3">
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-semibold mb-1">
                      Repository
                    </p>
                    <a
                      href={group.github_repo_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-primary hover:underline break-all font-mono leading-snug"
                    >
                      {group.github_repo_url.replace('https://github.com/', '')}
                    </a>
                  </div>
                  {group.github_branch && (
                    <div>
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-semibold mb-1 flex items-center gap-1">
                        <GitBranch size={11} />
                        Branch
                      </p>
                      <span className="text-xs font-mono text-foreground">
                        {group.github_branch}
                      </span>
                    </div>
                  )}
                </div>
                {repoError && (
                  <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                    {repoError}
                  </p>
                )}
                {repoSuccess && (
                  <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
                    {repoSuccess}
                  </p>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(true);
                      setRepoSuccess('');
                      setRepoError('');
                    }}
                    disabled={repoSaving}
                    className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                  >
                    Update Branch
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmRemove(true)}
                    disabled={repoSaving}
                    className="w-full px-4 py-2 rounded-md border border-destructive/30 text-sm font-semibold text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {repoSaving ? 'Removing…' : 'Remove'}
                  </button>
                </div>
              </div>
            ) : (
              <form
                onSubmit={handleSaveGroupRepo}
                className="rounded-lg bg-card border border-border p-5 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
                    <Github size={16} />
                    Group GitHub Repo
                  </h2>
                  {editing && group.github_repo_url && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false);
                        setRepoUrl(group.github_repo_url);
                        setRepoBranch(group.github_branch || '');
                        setRepoError('');
                        setRepoSuccess('');
                        setVerified(true);
                        setBranches(
                          group.github_branch ? [group.github_branch] : []
                        );
                      }}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  This repo and branch will be applied to all students in this
                  group.
                </p>
                <div className="space-y-2">
                  <input
                    value={repoUrl}
                    onChange={(e) => {
                      setRepoUrl(e.target.value);
                      setVerified(false);
                      setBranches([]);
                      setRepoBranch('');
                      setRepoSuccess('');
                      setRepoError('');
                    }}
                    placeholder="https://github.com/owner/repo"
                    className={inputClass}
                  />
                  <button
                    type="button"
                    onClick={handleVerifyRepo}
                    disabled={verifying || !repoUrl.trim()}
                    className="w-full px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {verifying ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        Verifying…
                      </span>
                    ) : (
                      'Verify Repository'
                    )}
                  </button>
                </div>
                {verified && branches.length > 0 && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      Branch
                    </label>
                    <select
                      value={repoBranch}
                      onChange={(e) => setRepoBranch(e.target.value)}
                      className={`${inputClass} cursor-pointer`}
                    >
                      {branches.map((b) => (
                        <option key={b} value={b}>
                          {b}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {repoError && (
                  <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                    {repoError}
                  </p>
                )}
                {repoSuccess && (
                  <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
                    {repoSuccess}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={repoSaving || !verified}
                  className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
                >
                  {repoSaving ? 'Saving…' : 'Save Repo'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>

      <DeleteConfirmDialog
        open={confirmRemove}
        title="Remove GitHub Repository"
        message="Are you sure you want to remove this group's GitHub repository and branch? This will also remove it from all students in this group."
        confirmLabel="Remove"
        loading={repoSaving}
        onCancel={() => setConfirmRemove(false)}
        onConfirm={async () => {
          setConfirmRemove(false);
          await handleRemoveGroupRepo();
        }}
      />
    </div>
  );
}
