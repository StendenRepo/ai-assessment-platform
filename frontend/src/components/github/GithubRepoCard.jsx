'use client';

import { useState } from 'react';
import { Github, GitBranch } from 'lucide-react';
import { verifyGithubRepo } from '@/lib/api/modulesApi';
import DeleteConfirmDialog from '@/components/common/DeleteConfirmDialog';

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

/**
 * Shared GitHub repository card used on both the group and student pages.
 *
 * Props:
 *   title          – heading text, e.g. "Group GitHub Repo"
 *   description    – optional sub-heading shown in edit mode
 *   savedUrl       – currently stored github_repo_url (or null/undefined)
 *   savedBranch    – currently stored github_branch (or null/undefined)
 *   onSave(url, branch) → Promise   – called when Save Repo is submitted
 *   onRemove()          → Promise   – called when Remove is clicked
 */
export default function GithubRepoCard({
  title,
  description,
  savedUrl,
  savedBranch,
  onSave,
  onRemove,
}) {
  const hasSaved = Boolean(savedUrl);

  const [editing, setEditing] = useState(!hasSaved);
  const [repoUrl, setRepoUrl] = useState(savedUrl || '');
  const [repoBranch, setRepoBranch] = useState(savedBranch || '');
  const [branches, setBranches] = useState(
    hasSaved && savedBranch ? [savedBranch] : []
  );
  const [verified, setVerified] = useState(hasSaved);
  const [verifying, setVerifying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [confirmRemove, setConfirmRemove] = useState(false);

  const handleVerify = async () => {
    setError('');
    setSuccess('');
    setVerified(false);
    setBranches([]);
    setRepoBranch('');
    if (!repoUrl.trim()) {
      setError('Enter a GitHub repository URL first.');
      return;
    }
    setVerifying(true);
    try {
      const result = await verifyGithubRepo(repoUrl.trim());
      setBranches(result.branches);
      setRepoBranch(result.default_branch);
      setVerified(true);
      setSuccess(
        `Repository verified. ${result.branches.length} branch${result.branches.length !== 1 ? 'es' : ''} found.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setVerifying(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (!verified) {
      setError('Please verify the repository before saving.');
      return;
    }
    setSaving(true);
    try {
      await onSave(repoUrl.trim(), repoBranch);
      setEditing(false);
      setSuccess('Repository and branch saved.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    setConfirmRemove(false);
    setError('');
    setSuccess('');
    setSaving(true);
    try {
      await onRemove();
      setRepoUrl('');
      setRepoBranch('');
      setBranches([]);
      setVerified(false);
      setEditing(true);
      setSuccess('Repository removed.');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const cancelEdit = () => {
    setEditing(false);
    setRepoUrl(savedUrl || '');
    setRepoBranch(savedBranch || '');
    setBranches(savedBranch ? [savedBranch] : []);
    setVerified(true);
    setError('');
    setSuccess('');
  };

  return (
    <div className="rounded-lg bg-card border border-border p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
          <Github size={16} />
          {title}
        </h2>
        {editing && savedUrl && (
          <button
            type="button"
            onClick={cancelEdit}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      {!editing && savedUrl ? (
        /* ── Saved view ── */
        <>
          {/* GitHub Configuration Section */}
          <div className="space-y-3 pb-3 border-b border-border">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-semibold mb-1">
                Repository
              </p>
              <a
                href={savedUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-primary hover:underline break-all font-mono leading-snug"
              >
                {savedUrl.replace('https://github.com/', '')}
              </a>
            </div>
            {savedBranch && (
              <div>
                <p className="text-[10px] text-muted-foreground uppercase tracking-wide font-semibold mb-1 flex items-center gap-1">
                  <GitBranch size={11} />
                  Branch
                </p>
                <span className="text-xs font-mono text-foreground">
                  {savedBranch}
                </span>
              </div>
            )}
          </div>

          {/* Status Messages Section */}
          {(error || success) && (
            <div className="space-y-2 pb-3 border-b border-border">
              {error && (
                <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                  {error}
                </p>
              )}
              {success && (
                <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
                  {success}
                </p>
              )}
            </div>
          )}

          {/* Actions Section */}
          <div className="grid grid-cols-2 gap-2 pt-1">
            <button
              type="button"
              onClick={() => {
                setEditing(true);
                setSuccess('');
                setError('');
              }}
              disabled={saving}
              className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
            >
              Update Branch
            </button>
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              disabled={saving}
              className="w-full px-4 py-2 rounded-md border border-destructive/30 text-sm font-semibold text-destructive hover:bg-destructive/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Removing…' : 'Remove'}
            </button>
          </div>
        </>
      ) : (
        /* ── Edit / new view ── */
        <form onSubmit={handleSave} className="space-y-4">
          {description && (
            <p className="text-xs text-muted-foreground pb-2 border-b border-border">
              {description}
            </p>
          )}

          {/* Repository Input Section */}
          <div className="space-y-2 pb-3 border-b border-border">
            <input
              value={repoUrl}
              onChange={(e) => {
                setRepoUrl(e.target.value);
                setVerified(false);
                setBranches([]);
                setRepoBranch('');
                setSuccess('');
                setError('');
              }}
              placeholder="https://github.com/owner/repo"
              className={inputClass}
            />
            <button
              type="button"
              onClick={handleVerify}
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

          {/* Branch Selection Section */}
          {verified && branches.length > 0 && (
            <div className="space-y-1.5 pb-3 border-b border-border">
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

          {/* Status Messages Section */}
          {(error || success) && (
            <div className="space-y-2 pb-3 border-b border-border">
              {error && (
                <p className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
                  {error}
                </p>
              )}
              {success && (
                <p className="rounded-md bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 text-xs text-emerald-400">
                  {success}
                </p>
              )}
            </div>
          )}

          {/* Submit Button Section */}
          <button
            type="submit"
            disabled={saving || !verified}
            className="w-full px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
          >
            {saving ? 'Saving…' : 'Save Repo'}
          </button>
        </form>
      )}

      <DeleteConfirmDialog
        open={confirmRemove}
        title="Remove Repository"
        message={
          <>
            Remove{' '}
            <span className="font-semibold text-foreground">
              {savedUrl
                ? savedUrl.replace('https://github.com/', '')
                : 'this repository'}
            </span>{' '}
            from this entry? This will also clear the branch setting.
          </>
        }
        confirmLabel="Remove"
        loading={saving}
        onConfirm={handleRemove}
        onCancel={() => setConfirmRemove(false)}
      />
    </div>
  );
}
