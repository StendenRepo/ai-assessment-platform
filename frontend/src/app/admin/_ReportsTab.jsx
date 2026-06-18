'use client';

import { useEffect, useState } from 'react';
import { Download, FileText, Package, Users } from 'lucide-react';
import {
  listAllReports,
  exportStudentDossier,
  exportModuleArchive,
  exportGradesExcel,
} from '@/lib/api/modulesApi';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(isoString) {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleString('nl-NL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const REPORT_ICONS = {
  'student.dossier_exported': Package,
  'module.archive_exported': Users,
  'grades.exported': FileText,
};

const ACTION_LABELS = {
  'student.dossier_exported': 'Individual Dossier',
  'module.archive_exported': 'Group Archive',
  'grades.exported': 'Grade Export',
};

function reportTitle(report) {
  if (report.action === 'student.dossier_exported') {
    return report.student_name
      ? `${report.student_name} — Individual Dossier`
      : 'Individual Student Dossier';
  }
  if (report.action === 'module.archive_exported') {
    return report.module_name
      ? `${report.module_name} — Group Archive`
      : 'Group Overview Archive';
  }
  if (report.action === 'grades.exported') {
    return report.module_name
      ? `${report.module_name} — Grade Export`
      : 'Grade Export (Excel)';
  }
  return report.label || report.action;
}

// ─── Row ──────────────────────────────────────────────────────────────────────

function ReportRow({ report }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');

  const canDownload =
    (report.action === 'student.dossier_exported' && report.student_id) ||
    (report.action === 'module.archive_exported' && report.module_id) ||
    (report.action === 'grades.exported' && report.module_id);

  const handleDownload = async () => {
    setDownloading(true);
    setError('');
    try {
      let blob, filename;
      const fmt = report.format || 'zip';

      if (report.action === 'student.dossier_exported') {
        ({ blob, filename } = await exportStudentDossier(
          report.student_id,
          report.student_name || '',
          fmt
        ));
      } else if (report.action === 'module.archive_exported') {
        ({ blob, filename } = await exportModuleArchive(
          report.module_id,
          report.module_name || '',
          fmt
        ));
      } else if (report.action === 'grades.exported') {
        ({ blob, filename } = await exportGradesExcel(
          report.module_id,
          report.module_name || ''
        ));
      }

      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      setError(err.message || 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  const ReportIcon = REPORT_ICONS[report.action] ?? FileText;

  return (
    <tr className="border-b border-border last:border-0 hover:bg-secondary/30 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
            <ReportIcon size={13} className="text-primary" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-foreground truncate max-w-[260px]">
              {reportTitle(report)}
            </div>
            {error && <p className="text-[11px] text-red-400 mt-0.5">{error}</p>}
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
        {ACTION_LABELS[report.action] ?? report.action}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
        {report.teacher_name || '—'}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
        {formatDate(report.timestamp)}
      </td>
      <td className="px-4 py-3 text-right">
        {canDownload && (
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 transition-colors ml-auto disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {downloading ? (
              <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <Download size={13} />
            )}
            {downloading ? 'Downloading…' : 'Download'}
          </button>
        )}
      </td>
    </tr>
  );
}

// ─── Tab ──────────────────────────────────────────────────────────────────────

export function ReportsTab() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    listAllReports(200)
      .then((data) => setReports(Array.isArray(data) ? data : []))
      .catch((e) => setError(e.message || 'Failed to load reports'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-foreground">All Report Exports</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          All exports generated by all teachers across the platform.
        </p>
      </div>

      <div className="rounded-lg border border-border overflow-hidden bg-card">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="px-6 py-8 text-center text-sm text-red-400">{error}</div>
        ) : reports.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground">
            No reports exported yet.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-secondary/50">
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Report</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Type</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Teacher</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Date</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <ReportRow key={report.id} report={report} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
