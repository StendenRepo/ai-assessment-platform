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
  X,
  Package,
  AlertTriangle,
  Activity,
} from 'lucide-react';
import {
  listModules,
  listProjectStudents,
  exportStudentDossier,
  exportModuleArchive,
} from '@/lib/api/modulesApi';
import { apiRequest } from '@/lib/api/apiClient';

// Fetch overlap signals for a module (teacher-only, internal)
async function fetchOverlapSignals(moduleId) {
  return apiRequest(`/modules/${moduleId}/overlap/signals`, {
    basePath: '/api/v1',
    onUnauthorized: false,
    errorMessage: (data, res) => data.detail || `Request failed (${res.status})`,
  });
}

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

const inputClass =
  'bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

// ─── Individual Student Report Modal ─────────────────────────────────────────

function IndividualReportModal({ open, onClose, moduleId, moduleName }) {
  const [students, setStudents] = useState([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [selectedStudentId, setSelectedStudentId] = useState('');
  const [exportFormat, setExportFormat] = useState('zip');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  // Reset and load students when modal opens with a module
  useEffect(() => {
    setStudents([]);
    setSelectedStudentId('');
    setExportError('');
    if (!open || !moduleId) return;
    setLoadingStudents(true);
    listProjectStudents(moduleId)
      .then((data) => setStudents(Array.isArray(data) ? data : []))
      .catch((e) => setExportError(e.message))
      .finally(() => setLoadingStudents(false));
  }, [open, moduleId]);

  const handleExport = async () => {
    if (!selectedStudentId) return;
    const student = students.find((s) => s.id === selectedStudentId);
    setExporting(true);
    setExportError('');
    try {
      const { blob, filename } = await exportStudentDossier(
        selectedStudentId,
        student?.name ?? '',
        exportFormat
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Dialog */}
      <div className="relative z-10 w-full max-w-md rounded-xl bg-card border border-border shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Package size={15} className="text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Individual Student Report</h2>
              <p className="text-xs text-muted-foreground truncate max-w-[220px]">{moduleName || 'Select a student to export'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-secondary"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          {/* No module selected warning */}
          {!moduleId && (
            <div className="rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-2.5">
              <p className="text-xs text-amber-400">Please select a module on the report page first.</p>
            </div>
          )}

          {/* Student */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Student *</label>
            <select
              value={selectedStudentId}
              onChange={(e) => setSelectedStudentId(e.target.value)}
              className={`w-full ${inputClass} cursor-pointer`}
              disabled={!moduleId || loadingStudents || students.length === 0}
            >
              <option value="">
                {!moduleId
                  ? '— Select a module first —'
                  : loadingStudents
                  ? 'Loading students…'
                  : students.length === 0
                  ? 'No students found'
                  : '— Choose a student —'}
              </option>
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}{s.student_number ? ` (${s.student_number})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Archive format */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Archive Format *</label>
            <div className="flex gap-2">
              {[
                { value: 'zip', label: 'ZIP', hint: 'Standard — works on all systems' },
                { value: 'tar', label: 'TAR.GZ', hint: 'Use if ZIP is blocked by school IT' },
              ].map((fmt) => (
                <button
                  key={fmt.value}
                  onClick={() => setExportFormat(fmt.value)}
                  className={`flex-1 py-2 px-3 rounded-md text-sm font-semibold transition-all text-left ${
                    exportFormat === fmt.value
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary border border-border text-muted-foreground hover:text-foreground hover:bg-secondary/80'
                  }`}
                >
                  <div>{fmt.label}</div>
                  <div className={`text-[10px] font-normal mt-0.5 ${exportFormat === fmt.value ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                    {fmt.hint}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Contains all evidence files and a plain-text summary (dossier.txt).
          </p>

          {exportError && (
            <p className="text-xs text-red-400">{exportError}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 justify-end px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={!selectedStudentId || exporting}
            className="flex items-center gap-2 px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exporting ? (
              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <Download size={14} />
            )}
            {exporting ? 'Exporting…' : `Download ${exportFormat === 'tar' ? 'TAR.GZ' : 'ZIP'}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Group Overview Modal ─────────────────────────────────────────────────────

function GroupOverviewModal({ open, onClose, moduleId, moduleName }) {
  const [exportFormat, setExportFormat] = useState('zip');
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');

  useEffect(() => {
    if (!open) {
      setExportFormat('zip');
      setExporting(false);
      setExportError('');
    }
  }, [open]);

  const handleExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      const { blob, filename } = await exportModuleArchive(moduleId, moduleName, exportFormat);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-xl bg-card border border-border shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Users size={15} className="text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">Group Overview Report</h2>
              <p className="text-xs text-muted-foreground truncate max-w-[220px]">{moduleName || '—'}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-secondary">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          {!moduleId && (
            <div className="rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-2.5">
              <p className="text-xs text-amber-400">Please select a module on the report page first.</p>
            </div>
          )}

          {/* Archive format */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">Archive Format *</label>
            <div className="flex gap-2">
              {[
                { value: 'zip', label: 'ZIP', hint: 'Standard — works on all systems' },
                { value: 'tar', label: 'TAR.GZ', hint: 'Use if ZIP is blocked by school IT' },
              ].map((fmt) => (
                <button
                  key={fmt.value}
                  onClick={() => setExportFormat(fmt.value)}
                  className={`flex-1 py-2 px-3 rounded-md text-sm font-semibold transition-all text-left ${
                    exportFormat === fmt.value
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary border border-border text-muted-foreground hover:text-foreground hover:bg-secondary/80'
                  }`}
                >
                  <div>{fmt.label}</div>
                  <div className={`text-[10px] font-normal mt-0.5 ${exportFormat === fmt.value ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}>
                    {fmt.hint}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Contains rubric, module book, all student evidence, assessment forms, and a grade list.
          </p>

          {exportError && <p className="text-xs text-red-400">{exportError}</p>}
        </div>

        {/* Footer */}
        <div className="flex gap-3 justify-end px-6 py-4 border-t border-border">
          <button onClick={onClose} className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={!moduleId || exporting}
            className="flex items-center gap-2 px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {exporting ? (
              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <Download size={14} />
            )}
            {exporting ? 'Exporting…' : `Download ${exportFormat === 'tar' ? 'TAR.GZ' : 'ZIP'}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── AI Analysis Modal ────────────────────────────────────────────────────────

const confidenceColor = (c) => {
  if (c >= 0.8) return 'text-red-400';
  if (c >= 0.5) return 'text-amber-400';
  return 'text-yellow-400';
};

function AIAnalysisModal({ open, onClose, moduleId, moduleName }) {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setSignals([]);
    setError('');
    if (!open || !moduleId) return;
    setLoading(true);
    fetchOverlapSignals(moduleId)
      .then((data) => setSignals(Array.isArray(data) ? data : []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [open, moduleId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl rounded-xl bg-card border border-border shadow-2xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Bot size={15} className="text-primary" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-foreground">AI Analysis — Overlap Signals</h2>
              <p className="text-xs text-muted-foreground truncate max-w-[300px]">{moduleName || '—'} · Internal view only</p>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-secondary">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 overflow-y-auto flex-1">
          {!moduleId ? (
            <div className="rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-2.5">
              <p className="text-xs text-amber-400">Please select a module on the report page first.</p>
            </div>
          ) : loading ? (
            <div className="flex justify-center py-10">
              <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : error ? (
            <p className="text-xs text-red-400">{error}</p>
          ) : signals.length === 0 ? (
            <div className="text-center py-10">
              <div className="text-2xl mb-2">✓</div>
              <p className="text-sm font-medium text-foreground">No overlap signals detected</p>
              <p className="text-xs text-muted-foreground mt-1">No suspicious patterns found for this module.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {signals.map((sig) => (
                <div key={sig.id} className="rounded-lg border border-border p-4 space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle size={13} className="text-amber-400 shrink-0" />
                      <span className="text-xs font-semibold text-foreground capitalize">{sig.overlap_type} overlap</span>
                    </div>
                    <span className={`text-xs font-bold font-mono ${confidenceColor(sig.confidence)}`}>
                      {Math.round(sig.confidence * 100)}% confidence
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                    <div>
                      <span className="font-medium text-foreground">Student A:</span> {sig.student_a_name}
                      <div className="text-[11px] font-mono truncate">{sig.evidence_a_name}</div>
                    </div>
                    <div>
                      <span className="font-medium text-foreground">Student B:</span> {sig.student_b_name}
                      <div className="text-[11px] font-mono truncate">{sig.evidence_b_name}</div>
                    </div>
                  </div>
                  {sig.snippet && (
                    <div className="rounded bg-background border border-border px-3 py-2 text-[11px] font-mono text-muted-foreground leading-relaxed line-clamp-3">
                      {sig.snippet}
                    </div>
                  )}
                  <div className="text-[10px] text-muted-foreground">
                    Detected: {sig.detected_at ? new Date(sig.detected_at).toLocaleDateString('nl-NL') : '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end px-6 py-4 border-t border-border shrink-0">
          <button onClick={onClose} className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Reports Page ─────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [modules, setModules] = useState([]);
  const [loadingModules, setLoadingModules] = useState(true);
  const [modulesError, setModulesError] = useState('');
  const [selectedProject, setSelectedProject] = useState('');
  const [reportType, setReportType] = useState('individual');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [modalOpen, setModalOpen] = useState(false);
  const [groupModalOpen, setGroupModalOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);

  useEffect(() => {
    listModules()
      .then((data) => {
        setModules(data);
        setModulesError('');
      })
      .catch((e) => setModulesError(e.message))
      .finally(() => setLoadingModules(false));
  }, []);

  const isIndividual = reportType === 'individual';
  const isGroup = reportType === 'group';
  const isAiInsights = reportType === 'ai-insights';
  // Hide export format for types that use their own modal
  const showExportFormat = !isIndividual && !isGroup && !isAiInsights;

  const handleGenerate = () => {
    if (isIndividual) setModalOpen(true);
    else if (isGroup) setGroupModalOpen(true);
    else if (isAiInsights) setAiModalOpen(true);
  };

  const selectedModule = modules.find((m) => m.id === selectedProject);

  return (
    <>
      <IndividualReportModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        moduleId={selectedProject}
        moduleName={selectedModule?.name ?? ''}
      />
      <GroupOverviewModal
        open={groupModalOpen}
        onClose={() => setGroupModalOpen(false)}
        moduleId={selectedProject}
        moduleName={selectedModule?.name ?? ''}
      />
      <AIAnalysisModal
        open={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        moduleId={selectedProject}
        moduleName={selectedModule?.name ?? ''}
      />

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
                  Select Module *
                </label>
                <select
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                  className={`w-full ${inputClass} cursor-pointer`}
                  disabled={loadingModules || !!modulesError}
                >
                  <option value="">
                    {loadingModules
                      ? 'Loading modules...'
                      : modulesError
                        ? 'Failed to load modules'
                        : '— Choose a module —'}
                  </option>
                  {modules.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                      {p.academic_year ? ` — ${p.academic_year}` : ''}
                    </option>
                  ))}
                </select>
                {modulesError && (
                  <p className="text-xs text-red-400">{modulesError}</p>
                )}
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

              {/* Export format — hidden for Individual and AI Insights (handled by modals) */}
              {showExportFormat && (
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
              )}

              <div className="flex gap-3 justify-end pt-4 border-t border-border">
                <button className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                  Preview
                </button>
                <button
                  onClick={handleGenerate}
                  className="px-5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
                >
                  {isIndividual ? 'Export Student Report →' : isAiInsights ? 'View AI Signals →' : 'Generate Report →'}
                </button>
              </div>
            </div>

            <div className="rounded-lg bg-card border border-border overflow-hidden">
              <div className="px-6 py-4 border-b border-border">
                <h2 className="text-sm font-semibold text-foreground">
                  Recent Reports
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
    </>
  );
}
