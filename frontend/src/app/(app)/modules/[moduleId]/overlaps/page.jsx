'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { ArrowRight, FileText, Loader2, ScanSearch } from 'lucide-react';
import {
  analyzeModuleOverlap,
  listModuleOverlapSignals,
} from '@/lib/api/modulesApi';
import { APP_PATHS } from '@/lib/routes';
import OverlapStatusBadge, {
  IntegrityTypeBadge,
} from '@/components/overlaps/OverlapStatusBadge';
import OverlapSignalMetrics, {
  integrityAccentClass,
} from '@/components/overlaps/OverlapSignalMetrics';
import ScanProgressBar from '@/components/overlaps/ScanProgressBar';
import {
  OVERLAP_REVIEW_DISCLAIMER,
  overlapStatusLabel,
} from '@/lib/overlapLabels';

const selectCls =
  'h-9 bg-secondary border border-border rounded-md pl-3 pr-8 text-sm text-foreground cursor-pointer focus:outline-none focus:ring-2 focus:ring-ring';

export default function ModuleOverlapsPage() {
  const { moduleId } = useParams();
  const searchParams = useSearchParams();
  const groupFilter = searchParams.get('group_id') || '';
  const [tab, setTab] = useState('confirmed');
  const [scopeFilter, setScopeFilter] = useState('all');
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { status: tab };
      if (scopeFilter !== 'all') params.scope = scopeFilter;
      if (groupFilter) params.group_id = groupFilter;
      const rows = await listModuleOverlapSignals(moduleId, params);
      setSignals(rows);
    } catch (e) {
      setError(e.message);
      setSignals([]);
    } finally {
      setLoading(false);
    }
  }, [moduleId, tab, scopeFilter, groupFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const runScan = async () => {
    setScanning(true);
    setError(null);
    try {
      await analyzeModuleOverlap(moduleId);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Overlap review</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Classifier and similarity indicators to support manual review — not
            definitive findings. Scores are estimates; always verify before
            academic action.
          </p>
        </div>
        <button
          type="button"
          onClick={runScan}
          disabled={scanning}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 disabled:opacity-60 shrink-0"
        >
          {scanning ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <ScanSearch size={16} />
          )}
          {scanning ? 'Scanning…' : 'Scan module'}
        </button>
      </div>

      <p className="text-xs text-muted-foreground border border-border/60 rounded-md px-3 py-2 bg-secondary/20">
        {OVERLAP_REVIEW_DISCLAIMER}
      </p>

      <ScanProgressBar active={scanning} />

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-md px-4 py-2">
          {error}
        </p>
      )}

      <div className="rounded-lg bg-card border border-border overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-5 py-3 border-b border-border bg-secondary/20">
          <div className="flex items-center gap-1">
            {['confirmed', 'possible'].map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  tab === key
                    ? 'bg-background text-foreground shadow-sm ring-1 ring-border'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                {overlapStatusLabel(key)}
              </button>
            ))}
          </div>
          <select
            value={scopeFilter}
            onChange={(e) => setScopeFilter(e.target.value)}
            className={`w-auto min-w-[9rem] shrink-0 ${selectCls}`}
            aria-label="Filter by scope"
          >
            <option value="all">All scopes</option>
            <option value="within_group">Within group</option>
            <option value="cross_group">Cross-group</option>
          </select>
        </div>

        {loading ? (
          <div className="py-12 flex justify-center">
            <Loader2 className="animate-spin text-muted-foreground" size={24} />
          </div>
        ) : signals.length === 0 ? (
          <p className="px-5 py-10 text-sm text-muted-foreground text-center">
            No {tab} overlaps. Upload evidence and run a scan.
          </p>
        ) : (
          <div className="divide-y divide-border">
            {signals.map((item) => {
              const integrityType = item.integrity_type || 'student_plagiarism';
              const fileLabel =
                integrityType === 'ai'
                  ? item.evidence_a_name
                  : `${item.evidence_a_name} · ${item.evidence_b_name}`;

              return (
                <Link
                  key={item.id}
                  href={APP_PATHS.moduleOverlapDetail(moduleId, item.id)}
                  className={`flex items-center gap-5 px-5 py-4 border-l-[3px] hover:bg-secondary/40 transition-colors group ${integrityAccentClass(integrityType)}`}
                >
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">
                        {integrityType === 'ai'
                          ? item.student_a_name
                          : `${item.student_a_name} ↔ ${item.student_b_name}`}
                      </span>
                      <IntegrityTypeBadge type={integrityType} />
                      <OverlapStatusBadge kind={item.status} />
                      {item.scope && <OverlapStatusBadge kind={item.scope} />}
                    </div>
                    <p className="flex items-center gap-1.5 text-xs text-muted-foreground min-w-0">
                      <FileText size={12} className="shrink-0 opacity-60" />
                      <span className="truncate">{fileLabel}</span>
                    </p>
                  </div>

                  <div className="flex items-center gap-4 shrink-0">
                    <OverlapSignalMetrics signal={item} compact />
                    <ArrowRight
                      size={16}
                      className="text-muted-foreground/60 group-hover:text-foreground transition-colors"
                    />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
