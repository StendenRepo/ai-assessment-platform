'use client';

import { useState, useEffect } from 'react';
import { Mail, X, Copy, ExternalLink, CheckCircle2 } from 'lucide-react';

/**
 * EmailDraftModal
 *
 * Generates a pre-filled email draft for sending the final assessment to a
 * student. The teacher can edit every field before opening their mail client.
 * The system never sends automatically — it only opens a mailto: link.
 *
 * Props:
 *   student   – { name, student_number, grade }
 *   moduleName – string
 *   onClose   – () => void
 */
export default function EmailDraftModal({ student, moduleName, onClose }) {
  const grade = student?.grade || '—';
  const studentName = student?.name || 'Student';
  const studentNumber = student?.student_number || '';

  const defaultSubject = `Assessment Result – ${moduleName} – ${studentName}`;

  const defaultBody = `Dear ${studentName},

I am writing to inform you of the result of your final assessment for the module "${moduleName}".

Student number : ${studentNumber}
Module         : ${moduleName}
Final grade    : ${grade}

Please review the attached assessment report for detailed feedback on your performance. If you have any questions or would like to discuss the result, feel free to contact me.

Kind regards,
[Your name]
[Your contact details]`;

  const [to, setTo] = useState('');
  const [subject, setSubject] = useState(defaultSubject);
  const [body, setBody] = useState(defaultBody);
  const [copied, setCopied] = useState(false);

  // Close on Escape
  useEffect(() => {
    const handler = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const mailtoHref = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  const handleCopyBody = async () => {
    try {
      await navigator.clipboard.writeText(body);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: select the textarea
    }
  };

  const inputClass =
    'w-full bg-secondary border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-2xl bg-card border border-border rounded-xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-border shrink-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <Mail size={15} className="text-primary" />
          </div>
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-foreground">
              Email Draft — Final Assessment
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Edit the draft below, then open in your mail client. Nothing is
              sent automatically.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
          >
            <X size={16} />
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
          {/* Grade badge */}
          <div className="flex items-center gap-3 rounded-lg bg-secondary border border-border px-4 py-3">
            <div className="flex-1 min-w-0">
              <p className="text-xs text-muted-foreground">Student</p>
              <p className="text-sm font-semibold text-foreground">
                {studentName}{' '}
                <span className="font-mono text-muted-foreground text-xs">
                  ({studentNumber})
                </span>
              </p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-xs text-muted-foreground">Final Grade</p>
              <p className="text-lg font-bold text-foreground font-mono">
                {grade}
              </p>
            </div>
          </div>

          {/* To */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              To (student email)
            </label>
            <input
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="student@example.com"
              className={inputClass}
            />
          </div>

          {/* Subject */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Subject
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className={inputClass}
            />
          </div>

          {/* Body */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-muted-foreground">
                Message
              </label>
              <button
                type="button"
                onClick={handleCopyBody}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                {copied ? (
                  <>
                    <CheckCircle2 size={12} className="text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    Copy text
                  </>
                )}
              </button>
            </div>
            <textarea
              rows={12}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className={`${inputClass} resize-y font-mono text-xs leading-relaxed`}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-border shrink-0">
          <p className="text-xs text-muted-foreground">
            Opens your default mail client. You can still edit before sending.
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
            >
              Cancel
            </button>
            <a
              href={mailtoHref}
              onClick={onClose}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
            >
              <ExternalLink size={14} />
              Open in Mail
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
