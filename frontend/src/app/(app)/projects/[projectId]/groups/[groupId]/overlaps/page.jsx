'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  AlertTriangle,
  ArrowRight,
  Download,
  Loader2,
  ScanSearch,
} from 'lucide-react';
import { overlapApi } from '@/lib/overlapApi';
import OverlapStatusBadge from '@/components/overlaps/OverlapStatusBadge';
import { selectInlineCls } from '@/lib/formStyles';

export default function OverlapsListPage() {
  const { projectId, groupId } = useParams();
  const [tab, setTab] = useState('confirmed');
  const [scopeFilter, setScopeFilter] = useState('all');
  const [sort, setSort] = useState('similarity');
  const [order, setOrder] = useState('desc');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res =
        tab === 'possible'
          ? await overlapApi.listPossible(projectId, groupId, { sort, order })
          : await overlapApi.list(projectId, groupId, {
              status: tab,
              scope: scopeFilter === 'all' ? undefined : scopeFilter,
              sort,
              order,
            });
      setData(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [projectId, groupId, tab, scopeFilter, sort, order]);

  useEffect(() => {
    load();
  }, [load]);

  const runDetect = async (full = false) => {
    setScanning(true);
    setError(null);
    try {
      if (full) {
        await overlapApi.detectAll(projectId);
      } else {
        await overlapApi.detect(projectId, groupId);
        await overlapApi.detectCrossGroup(projectId);
      }
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  const detailGroup = (item) =>
    item.scope === 'cross_group' ? item.group_a_id || groupId : groupId;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link
            href={`/projects/${projectId}/groups/${groupId}`}
            className="text-xs text-muted-foreground hover:text-primary transition-colors"
          >
            ← Back to group
          </Link>
          <h1 className="text-2xl font-bold text-foreground mt-2">
            Overlap review
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Compare student evidence and review similarity matches
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <a
            href={overlapApi.exportZip(projectId, groupId)}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-colors"
          >
            <Download size={16} />
            Export report
          </a>
          <button
            type="button"
            onClick={() => runDetect(false)}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 rounded-md border border-border text-sm font-semibold text-foreground hover:bg-secondary transition-colors disabled:opacity-50"
          >
            {scanning ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <ScanSearch size={16} />
            )}
            Scan group
          </button>
          <button
            type="button"
            onClick={() => runDetect(true)}
            disabled={scanning}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            Full project scan
          </button>
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-3">
          {error}
        </p>
      )}

      <div className="rounded-lg bg-card border border-border overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 px-5 pt-2 border-b border-border">
          <div className="flex border-b border-border lg:border-b-0 -mb-px lg:mb-0">
            {[
              { id: 'confirmed', label: 'Confirmed', count: data?.confirmed_count },
              { id: 'possible', label: 'Possible', count: data?.possible_count },
            ].map(({ id, label, count }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`px-6 py-3.5 text-sm font-medium transition-all border-b-2 whitespace-nowrap ${
                  tab === id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {label} ({count ?? 0})
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3 pb-4 lg:pb-3">
            <select
              value={scopeFilter}
              onChange={(e) => setScopeFilter(e.target.value)}
              className={selectInlineCls}
              aria-label="Filter by scope"
            >
              <option value="all">All scopes</option>
              <option value="within_group">Within group</option>
              <option value="cross_group">Cross-group</option>
            </select>
            <select
              value={`${sort}-${order}`}
              onChange={(e) => {
                const [s, o] = e.target.value.split('-');
                setSort(s);
                setOrder(o);
              }}
              className={selectInlineCls}
              aria-label="Sort overlaps"
            >
              <option value="similarity-desc">Similarity ↓</option>
              <option value="similarity-asc">Similarity ↑</option>
            </select>
          </div>
        </div>

        {data && (
          <div className="px-5 py-3 border-b border-border bg-secondary/20">
            <p className="text-xs text-muted-foreground">
              Within group:{' '}
              <span className="font-medium text-foreground">
                {data.within_group_count ?? 0}
              </span>
              {' · '}
              Cross-group:{' '}
              <span className="font-medium text-foreground">
                {data.cross_group_count ?? 0}
              </span>
            </p>
          </div>
        )}

        {loading ? (
          <div className="py-16 flex justify-center">
            <Loader2 className="animate-spin text-muted-foreground" size={24} />
          </div>
        ) : !data?.items?.length ? (
          <div className="p-12 text-center">
            <AlertTriangle
              className="mx-auto mb-3 text-muted-foreground"
              size={28}
            />
            <p className="text-sm font-medium text-foreground">
              No {tab} overlaps
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Run a scan to detect similar text between students
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {data.items.map((item) => (
              <Link
                key={item.id}
                href={`/projects/${projectId}/groups/${detailGroup(item)}/overlaps/${item.id}`}
                className="flex items-center gap-4 px-5 py-4 hover:bg-secondary/40 transition-colors group"
              >
                <OverlapStatusBadge
                  status={item.status}
                  percent={item.similarity_percent}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground">
                    {item.student_a_name}{' '}
                    <span className="text-muted-foreground font-normal">↔</span>{' '}
                    {item.student_b_name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">
                    {item.scope === 'cross_group'
                      ? `Cross-group · ${item.group_a_name} / ${item.group_b_name}`
                      : 'Within group'}
                    {' · '}
                    {item.file_a} · {item.file_b}
                  </p>
                </div>
                <ArrowRight
                  size={16}
                  className="text-muted-foreground group-hover:text-primary shrink-0 transition-colors"
                />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
