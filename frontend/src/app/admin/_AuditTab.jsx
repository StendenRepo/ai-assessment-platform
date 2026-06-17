'use client';

import { useEffect, useMemo, useState } from 'react';
import { adminFetch } from '@/lib/api/adminFetch';
import { Modal, Spinner } from './_ui';

const TECHNICAL_DETAIL_KEYS = new Set([
  'route',
  'path',
  'query',
  'path_params',
  'status_code',
  'teacher_name',
  'teacher_id',
  'assessment_id',
  'ip_address',
]);

function formatAction(action) {
  if (!action) return '—';
  const value = String(action)
    .replace(/[._-]+/g, ' ')
    .trim()
    .toLowerCase();
  if (!value) return '—';
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatLabel(key) {
  if (!key) return '—';
  return String(key)
    .replace(/[._-]+/g, ' ')
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function formatOperation(value) {
  if (!value) return null;
  const operationMap = {
    created: 'Added',
    updated: 'Changed',
    deleted: 'Removed',
    upload: 'Uploaded',
    replace: 'Replaced',
    delete: 'Removed',
  };
  return operationMap[String(value).toLowerCase()] || formatLabel(value);
}

function sourceLabel(value) {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'teacher') return 'Teacher action';
  if (normalized === 'ai') return 'AI-assisted action';
  if (normalized === 'system') return 'System action';
  return '—';
}

function detailEntries(details, action = '') {
  if (!details || typeof details !== 'object') return [];
  const clone = { ...details };
  const normalizedAction = String(action || '').toLowerCase();
  const hideProjectForGroupCreate = normalizedAction === 'group.created';

  // Build a set of keys to skip because old and new values are the same
  const skipKeys = new Set();
  Object.entries(clone).forEach(([key, value]) => {
    if (key.startsWith('new_')) {
      const oldKey = key.replace('new_', 'old_');
      if (clone[oldKey] !== undefined && clone[oldKey] === value) {
        skipKeys.add(oldKey);
        skipKeys.add(key);
      }
    }
  });
  const prioritized = [];
  if (clone.where) prioritized.push(['Where', clone.where]);
  if (clone.operation) {
    prioritized.push(['Operation', formatOperation(clone.operation)]);
  }
  if (clone.module_name) prioritized.push(['Module', clone.module_name]);
  if (clone.group_name) prioritized.push(['Group', clone.group_name]);
  if (clone.project_name && !hideProjectForGroupCreate) {
    prioritized.push(['Project', clone.project_name]);
  }
  if (clone.student_name) prioritized.push(['Student', clone.student_name]);
  if (clone.student_id) prioritized.push(['Student ID', clone.student_id]);
  if (clone.module_book_name)
    prioritized.push(['Module Book', clone.module_book_name]);
  if (clone.rubric_name) prioritized.push(['Rubric', clone.rubric_name]);
  if (clone.file_name) prioritized.push(['File', clone.file_name]);

  const extra = Object.entries(clone)
    .filter(([k, v]) => {
      if (skipKeys.has(k)) return false;
      if (TECHNICAL_DETAIL_KEYS.has(k)) return false;
      if (
        k === 'where' ||
        k === 'operation' ||
        k === 'module_name' ||
        k === 'group_name' ||
        (k === 'project_name' && !hideProjectForGroupCreate) ||
        k === 'student_name' ||
        k === 'student_id' ||
        k === 'module_book_name' ||
        k === 'rubric_name' ||
        k === 'file_name' ||
        k.endsWith('_id')
      ) {
        return false;
      }
      return v !== null && v !== undefined && String(v).trim() !== '';
    })
    .map(([k, v]) => [formatLabel(k), v]);

  return [...prioritized, ...extra].filter(([, v]) => v);
}

function formatDetails(details, action = '') {
  const entries = detailEntries(details, action);
  if (!entries.length) return '—';
  return entries
    .slice(0, 4)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join(' | ');
}

function EventMetaRow({ label, value }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 text-xs">
      <div className="text-muted-foreground">{label}</div>
      <div className="text-foreground break-all">{value || '—'}</div>
    </div>
  );
}

export function AuditTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const data = await adminFetch('/audit-events?limit=200');
        if (!cancelled) {
          setItems(Array.isArray(data) ? data : []);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e.message || 'Could not load audit logs');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) => {
      const haystack = [
        item.action,
        item.teacher_name,
        item.teacher_id,
        item.assessment_id,
        item.source,
        item.details_json ? JSON.stringify(item.details_json) : '',
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [items, query]);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-500 py-4">{error}</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-muted-foreground">
          {filtered.length} audit event{filtered.length !== 1 ? 's' : ''}
        </p>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by action, teacher, or source"
          className="w-72 bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
        />
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-secondary">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Timestamp
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Teacher
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Action
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Source
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No audit events found.
                </td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr
                  key={item.id}
                  className="hover:bg-secondary/50 transition-colors cursor-pointer"
                  onClick={() => setSelected(item)}
                >
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                    {item.timestamp
                      ? new Date(item.timestamp).toLocaleString()
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {item.teacher_name || 'System'}
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground">
                    {formatAction(item.action)}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {sourceLabel(item.source)}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {formatDetails(item.details_json, item.action)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <Modal title="Activity Details" onClose={() => setSelected(null)}>
          <div className="space-y-3">
            <EventMetaRow
              label="When"
              value={
                selected.timestamp
                  ? new Date(selected.timestamp).toLocaleString()
                  : '—'
              }
            />
            <EventMetaRow
              label="By"
              value={selected.teacher_name || 'System'}
            />
            <EventMetaRow label="Type" value={formatAction(selected.action)} />
            <EventMetaRow label="Source" value={sourceLabel(selected.source)} />

            {detailEntries(selected.details_json).length > 0 && (
              <>
                <div className="pt-2 border-t border-border" />
                {detailEntries(selected.details_json, selected.action).map(
                  ([label, value]) => (
                    <EventMetaRow
                      key={label}
                      label={label}
                      value={String(value)}
                    />
                  )
                )}
                {/* Metadata Section */}
                <div className="space-y-3 pb-3 border-b border-border">
                  <EventMetaRow
                    label="When"
                    value={
                      selected.timestamp
                        ? new Date(selected.timestamp).toLocaleString()
                        : '—'
                    }
                  />
                  <EventMetaRow
                    label="By"
                    value={selected.teacher_name || 'System'}
                  />
                  <EventMetaRow
                    label="Type"
                    value={formatAction(selected.action)}
                  />
                  <EventMetaRow
                    label="Source"
                    value={sourceLabel(selected.source)}
                  />
                </div>
                {/* Main Details Sections */}
                <div className="space-y-4">
                  {/* Name/Identity Changes */}
                  {detailEntries(selected.details_json, selected.action).filter(
                    ([label]) =>
                      label.toLowerCase().includes('name') ||
                      label.toLowerCase().includes('student') ||
                      label.toLowerCase().includes('module') ||
                      label.toLowerCase().includes('group') ||
                      label.toLowerCase().includes('project') ||
                      label.toLowerCase().includes('rubric') ||
                      label.toLowerCase().includes('book') ||
                      label.toLowerCase().includes('file') ||
                      label.toLowerCase().includes('where') ||
                      label.toLowerCase().includes('operation')
                  ).length > 0 && (
                    <div className="space-y-2 pb-3 border-b border-border">
                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Item Details
                      </h4>
                      <div className="space-y-3">
                        {detailEntries(selected.details_json, selected.action)
                          .filter(
                            ([label]) =>
                              label.toLowerCase().includes('name') ||
                              label.toLowerCase().includes('student') ||
                              label.toLowerCase().includes('module') ||
                              label.toLowerCase().includes('group') ||
                              label.toLowerCase().includes('project') ||
                              label.toLowerCase().includes('rubric') ||
                              label.toLowerCase().includes('book') ||
                              label.toLowerCase().includes('file') ||
                              label.toLowerCase().includes('where') ||
                              label.toLowerCase().includes('operation')
                          )
                          .map(([label, value]) => (
                            <EventMetaRow
                              key={label}
                              label={label}
                              value={String(value)}
                            />
                          ))}
                      </div>
                    </div>
                  )}
                  {/* GitHub Related Changes */}
                  {detailEntries(selected.details_json, selected.action).filter(
                    ([label]) =>
                      label.toLowerCase().includes('github') ||
                      label.toLowerCase().includes('repo') ||
                      label.toLowerCase().includes('branch')
                  ).length > 0 && (
                    <div className="space-y-2 pb-3 border-b border-border">
                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        GitHub Configuration
                      </h4>
                      <div className="space-y-3">
                        {detailEntries(selected.details_json, selected.action)
                          .filter(
                            ([label]) =>
                              label.toLowerCase().includes('github') ||
                              label.toLowerCase().includes('repo') ||
                              label.toLowerCase().includes('branch')
                          )
                          .map(([label, value]) => (
                            <EventMetaRow
                              key={label}
                              label={label}
                              value={String(value)}
                            />
                          ))}
                      </div>
                    </div>
                  )}
                  {/* Other Details */}
                  {detailEntries(selected.details_json, selected.action).filter(
                    ([label]) =>
                      !label.toLowerCase().includes('name') &&
                      !label.toLowerCase().includes('student') &&
                      !label.toLowerCase().includes('module') &&
                      !label.toLowerCase().includes('group') &&
                      !label.toLowerCase().includes('project') &&
                      !label.toLowerCase().includes('rubric') &&
                      !label.toLowerCase().includes('book') &&
                      !label.toLowerCase().includes('file') &&
                      !label.toLowerCase().includes('where') &&
                      !label.toLowerCase().includes('operation') &&
                      !label.toLowerCase().includes('github') &&
                      !label.toLowerCase().includes('repo') &&
                      !label.toLowerCase().includes('branch')
                  ).length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Additional Details
                      </h4>
                      <div className="space-y-3">
                        {detailEntries(selected.details_json, selected.action)
                          .filter(
                            ([label]) =>
                              !label.toLowerCase().includes('name') &&
                              !label.toLowerCase().includes('student') &&
                              !label.toLowerCase().includes('module') &&
                              !label.toLowerCase().includes('group') &&
                              !label.toLowerCase().includes('project') &&
                              !label.toLowerCase().includes('rubric') &&
                              !label.toLowerCase().includes('book') &&
                              !label.toLowerCase().includes('file') &&
                              !label.toLowerCase().includes('where') &&
                              !label.toLowerCase().includes('operation') &&
                              !label.toLowerCase().includes('github') &&
                              !label.toLowerCase().includes('repo') &&
                              !label.toLowerCase().includes('branch')
                          )
                          .map(([label, value]) => (
                            <EventMetaRow
                              key={label}
                              label={label}
                              value={String(value)}
                            />
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
