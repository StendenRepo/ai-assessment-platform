'use client';

import { useEffect, useState } from 'react';
import {
  Download,
  FileText,
  Users,
  Bot,
  Archive,
  Shield,
  ChevronRight,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { mockProjects } from '@/lib/mockData';
import { platformApi } from '@/lib/platformApi';
import { inputCls, selectFullCls } from '@/lib/formStyles';

const reportTypes = [
  {
    value: 'individual',
    label: 'Individual Student Reports',
    desc: 'Separate report per student with scores, feedback, and evidence overview',
    icon: FileText,
  },
  {
    value: 'group',
    label: 'Group Overview Report',
    desc: 'Comparison of all students with averages and score distribution',
    icon: Users,
  },
  {
    value: 'ai-insights',
    label: 'AI Analysis Report',
    desc: 'Overview of AI insights, overlap detections, and warnings',
    icon: Bot,
  },
  {
    value: 'evidence',
    label: 'Evidence Audit Report',
    desc: 'Complete audit of all evidence with traceability to sources',
    icon: Archive,
  },
];

const recentReports = [
  {
    name: 'E-Commerce Platform — Individual Reports',
    date: 'May 15, 2026 · 2:32 PM',
    format: 'PDF',
    files: 4,
  },
  {
    name: 'Machine Learning Model — AI Analysis',
    date: 'May 14, 2026 · 10:15 AM',
    format: 'Excel',
    files: 1,
  },
  {
    name: 'Mobile App Prototype — Group Overview',
    date: 'May 12, 2026 · 4:45 PM',
    format: 'PDF',
    files: 1,
  },
];

export default function ReportsPage() {
  const [selectedProject, setSelectedProject] = useState('');
  const [reportType, setReportType] = useState('individual');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [auditEntries, setAuditEntries] = useState([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditFilter, setAuditFilter] = useState('');

  const loadAudit = () => {
    setAuditLoading(true);
    platformApi
      .audit({ limit: 50, q: auditFilter || undefined })
      .then((data) => setAuditEntries(data.events || []))
      .catch(() => setAuditEntries([]))
      .finally(() => setAuditLoading(false));
  };

  useEffect(() => {
    loadAudit();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Reports & Export</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Generate and export assessment reports
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-5">
          <div className="rounded-lg bg-card border border-border p-6 space-y-5">
            <h2 className="text-sm font-semibold text-foreground">
              Report Configuration
            </h2>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Select Project *
              </label>
              <select
                value={selectedProject}
                onChange={(e) => setSelectedProject(e.target.value)}
                className={selectFullCls}
              >
                <option value="">— Choose a project —</option>
                {mockProjects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {p.course}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">
                Report Type *
              </label>
              <div className="space-y-2">
                {reportTypes.map(({ value, label, desc, icon: Icon }) => (
                  <label
                    key={value}
                    className={`flex items-start gap-4 rounded-lg border p-4 cursor-pointer transition-all ${reportType === value ? 'border-primary bg-primary/5' : 'border-border hover:border-border/80 hover:bg-secondary/50'}`}
                  >
                    <input
                      type="radio"
                      name="reportType"
                      value={value}
                      checked={reportType === value}
                      onChange={() => setReportType(value)}
                      className="mt-0.5 accent-primary"
                    />
                    <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                      <Icon size={15} className="text-primary" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-foreground">
                        {label}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {desc}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">
                Export Format *
              </label>
              <div className="flex gap-2">
                {['pdf', 'excel', 'csv', 'json'].map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => setExportFormat(fmt)}
                    className={`flex-1 py-2 rounded-md text-sm font-semibold uppercase tracking-wide transition-all ${exportFormat === fmt ? 'bg-primary text-primary-foreground' : 'bg-secondary border border-border text-muted-foreground hover:text-foreground hover:bg-secondary/80'}`}
                  >
                    {fmt}
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-border pt-4 space-y-2.5">
              <label className="text-xs font-medium text-muted-foreground">
                Options
              </label>
              {[
                { label: 'Include assessment criteria', checked: true },
                { label: 'Include AI analyses and suggestions', checked: true },
                {
                  label: 'Include evidence links and source files',
                  checked: false,
                },
                { label: 'Anonymize student data', checked: false },
              ].map((opt) => (
                <label
                  key={opt.label}
                  className="flex items-center gap-2.5 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    defaultChecked={opt.checked}
                    className="w-4 h-4 rounded accent-primary"
                  />
                  <span className="text-sm text-foreground">{opt.label}</span>
                </label>
              ))}
            </div>

            <div className="flex gap-3 justify-end pt-2 border-t border-border">
              <button className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                Preview
              </button>
              <button className="px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors">
                Generate Report →
              </button>
            </div>
          </div>

          <div className="rounded-lg bg-card border border-border overflow-hidden">
            <div className="px-6 py-4 border-b border-border flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-foreground">
                  Platform audit log
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Live events from POC backend (uploads, analysis, consent)
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={auditFilter}
                  onChange={(e) => setAuditFilter(e.target.value)}
                  placeholder="Filter…"
                  className={`w-36 ${inputCls}`}
                />
                <button
                  type="button"
                  onClick={loadAudit}
                  className="p-2 rounded-md border border-border hover:bg-secondary"
                  title="Refresh"
                >
                  <RefreshCw size={14} />
                </button>
              </div>
            </div>
            {auditLoading ? (
              <div className="py-10 flex justify-center">
                <Loader2 className="animate-spin text-muted-foreground" size={20} />
              </div>
            ) : auditEntries.length === 0 ? (
              <p className="px-6 py-8 text-sm text-muted-foreground text-center">
                No audit events yet. Upload evidence or run analysis to generate entries.
              </p>
            ) : (
              <div className="divide-y divide-border max-h-80 overflow-y-auto">
                {auditEntries.map((entry, i) => (
                  <div key={i} className="px-6 py-3 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-foreground font-mono">
                        {entry.action}
                      </span>
                      <span className="text-muted-foreground shrink-0">
                        {entry.timestamp
                          ? new Date(entry.timestamp).toLocaleString('en-US')
                          : '—'}
                      </span>
                    </div>
                    {entry.teacher && (
                      <p className="text-muted-foreground mt-0.5">
                        {entry.teacher}
                      </p>
                    )}
                    {entry.detail && (
                      <p className="text-muted-foreground mt-1 font-mono truncate">
                        {typeof entry.detail === 'string'
                          ? entry.detail
                          : JSON.stringify(entry.detail)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-lg bg-card border border-border overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground">
                Recent Reports (wireframe)
              </h2>
            </div>
            <div className="divide-y divide-border">
              {recentReports.map((report, i) => (
                <div key={i} className="flex items-center gap-4 px-6 py-4">
                  <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText size={15} className="text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-foreground">
                      {report.name}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {report.date} · {report.format} · {report.files} file
                      {report.files > 1 ? 's' : ''}
                    </div>
                  </div>
                  <button className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors shrink-0">
                    <Download size={13} /> Download
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-1 space-y-4">
          <div className="rounded-lg bg-card border border-border p-5 space-y-4 sticky top-4">
            <h3 className="text-sm font-semibold text-foreground">
              Report Types
            </h3>
            <div className="space-y-3">
              {reportTypes.map(({ value, label, desc, icon: Icon }) => (
                <button
                  key={value}
                  onClick={() => setReportType(value)}
                  className="w-full flex items-start gap-3 text-left rounded-md hover:bg-secondary p-2 transition-colors"
                >
                  <Icon size={14} className="text-primary mt-0.5 shrink-0" />
                  <div>
                    <div className="text-xs font-semibold text-foreground">
                      {label}
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                      {desc}
                    </div>
                  </div>
                  <ChevronRight
                    size={13}
                    className="text-muted-foreground shrink-0 mt-0.5"
                  />
                </button>
              ))}
            </div>
          </div>
          <div className="rounded-lg bg-secondary border border-border p-4 flex items-start gap-3">
            <Shield size={14} className="text-amber-400 shrink-0 mt-0.5" />
            <p className="text-xs text-muted-foreground leading-relaxed">
              Reports may contain sensitive student data. Share only with
              authorized personnel and handle per GDPR guidelines.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
