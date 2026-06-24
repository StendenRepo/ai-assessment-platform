'use client';

import { useState } from 'react';
import {
  User,
  Brain,
  Sun,
  Moon,
  Loader2,
  Download,
  FileSpreadsheet,
  KeyRound,
} from 'lucide-react';

import { useTheme } from '@/context/ThemeContext';
import { useNotifications } from '@/context/NotificationContext';
import { useAuth } from '@/context/AuthContext';
import { UI_STATUS_LABELS } from '@/lib/uiStatusLabels';

import {
  downloadStudentTemplate,
  downloadRubricTemplate,
} from '@/lib/api/modulesApi';

import { setPin as apiSetPin, removePin as apiRemovePin } from '@/lib/auth';

const tabs = [
  { key: 'general', label: 'General', icon: User },
  { key: 'security', label: 'Security', icon: KeyRound },
  { key: 'ai', label: 'AI Configuration', icon: Brain },
  { key: 'data', label: 'Data Management', icon: FileSpreadsheet },
];

const inputClass =
  'w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all';
const selectClass = `${inputClass} cursor-pointer`;

function Toggle({ defaultChecked, checked, onChange, disabled }) {
  const controlled = typeof checked === 'boolean';
  const [internalOn, setInternalOn] = useState(defaultChecked ?? false);
  const on = controlled ? checked : internalOn;

  const handleToggle = () => {
    if (disabled) return;
    const next = !on;
    if (!controlled) {
      setInternalOn(next);
    }
    onChange?.(next);
  };

  return (
    <button
      onClick={handleToggle}
      disabled={disabled}
      className={`relative w-10 h-5.5 rounded-full transition-colors ${on ? 'bg-primary' : 'bg-border'} ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${on ? 'translate-x-5' : 'translate-x-0'}`}
      />
    </button>
  );
}

function SectionCard({ title, children }) {
  return (
    <div className="rounded-lg bg-card border border-border p-6 space-y-4">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {children}
    </div>
  );
}

function LoginPinSection() {
  const { user, login } = useAuth();
  const [hasPin, setHasPin] = useState(Boolean(user?.has_pin));
  const [password, setPassword] = useState('');
  const [pin, setPinValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const applyUpdated = (updated) => {
    setHasPin(Boolean(updated.has_pin));
    login(updated);
    setPassword('');
    setPinValue('');
  };

  const handleSet = async () => {
    setMessage(null);
    setLoading(true);
    try {
      applyUpdated(await apiSetPin(password, pin));
      setMessage({
        type: 'success',
        text: 'PIN set. It will be required after your password next time you log in.',
      });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async () => {
    setMessage(null);
    setLoading(true);
    try {
      applyUpdated(await apiRemovePin(password));
      setMessage({ type: 'success', text: 'PIN removed.' });
    } catch (err) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <SectionCard title="Login PIN">
      <p className="text-xs text-muted-foreground">
        {hasPin
          ? 'A PIN is currently required after your password when you log in.'
          : 'Add an optional PIN for an extra step after your password at login.'}
      </p>
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-muted-foreground">
          Current password
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className={inputClass}
        />
      </div>
      {!hasPin && (
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            New PIN (4–6 digits)
          </label>
          <input
            type="password"
            inputMode="numeric"
            value={pin}
            onChange={(e) => setPinValue(e.target.value)}
            placeholder="••••"
            className={inputClass}
          />
        </div>
      )}
      {message && (
        <p
          className={`text-xs rounded-md px-3 py-2 ${message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20' : 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20'}`}
        >
          {message.text}
        </p>
      )}
      <div className="flex gap-2">
        {hasPin ? (
          <button
            onClick={handleRemove}
            disabled={loading || !password}
            className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-red-400 hover:border-red-500/30 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? UI_STATUS_LABELS.removing : 'Remove PIN'}
          </button>
        ) : (
          <button
            onClick={handleSet}
            disabled={loading || !password || !pin}
            className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? UI_STATUS_LABELS.saving : 'Set PIN'}
          </button>
        )}
      </div>
    </SectionCard>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('general');
  const { theme, setTheme } = useTheme();
  const { aiProcessingEnabled, setAiProcessingNotificationsEnabled } =
    useNotifications();
  const [templateDownloading, setTemplateDownloading] = useState(false);
  const [templateError, setTemplateError] = useState('');
  const [rubricDownloading, setRubricDownloading] = useState(false);
  const [rubricError, setRubricError] = useState('');

  const handleDownloadTemplate = async () => {
    setTemplateDownloading(true);
    setTemplateError('');
    try {
      const { blob, filename } = await downloadStudentTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setTemplateError(err.message || 'Failed to download template');
    } finally {
      setTemplateDownloading(false);
    }
  };

  const handleDownloadRubricTemplate = async () => {
    setRubricDownloading(true);
    setRubricError('');
    try {
      const { blob, filename } = await downloadRubricTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setRubricError(err.message || 'Failed to download template');
    } finally {
      setRubricDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your preferences and system configuration
        </p>
      </div>

      <div className="grid grid-cols-4 gap-6">
        <div className="col-span-1">
          <div className="rounded-lg bg-card border border-border overflow-hidden sticky top-4">
            {tabs.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`w-full flex items-center gap-3 px-4 py-3.5 text-sm font-medium transition-all border-l-2 ${activeTab === key ? 'border-primary bg-primary/5 text-primary' : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary'}`}
              >
                <Icon size={15} /> {label}
              </button>
            ))}
          </div>
        </div>

        <div className="col-span-3 space-y-5">
          {activeTab === 'general' && (
            <>
              <SectionCard title="Preferences">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      Language
                    </label>
                    <select className={`${inputClass} cursor-pointer`}>
                      <option value="en">English</option>
                      <option value="nl">Nederlands</option>
                      <option value="de">Deutsch</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      Date Format
                    </label>
                    <select className={`${inputClass} cursor-pointer`}>
                      <option>DD-MM-YYYY</option>
                      <option>MM-DD-YYYY</option>
                      <option>YYYY-MM-DD</option>
                    </select>
                  </div>
                </div>
                <div className="flex items-center justify-between pt-4 border-t border-border">
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      Theme
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Switch between light and dark appearance
                    </div>
                  </div>
                  <div className="flex rounded-md border border-border overflow-hidden">
                    <button
                      onClick={() => setTheme('light')}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all ${theme === 'light' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-secondary'}`}
                    >
                      <Sun size={13} /> Light
                    </button>
                    <button
                      onClick={() => setTheme('dark')}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border-l border-border transition-all ${theme === 'dark' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-secondary'}`}
                    >
                      <Moon size={13} /> Dark
                    </button>
                  </div>
                </div>
              </SectionCard>

              <SectionCard title="Notifications">
                <div className="space-y-4">
                  {[
                    {
                      label: 'Email for new projects',
                      sub: 'Get notified when a project is created',
                      on: true,
                    },
                    {
                      label: 'AI evidence processing updates',
                      sub: 'When AI processing succeeds or fails for uploaded evidence',
                      on: aiProcessingEnabled,
                      controlled: true,
                    },
                    {
                      label: 'Approaching deadlines',
                      sub: '3 days before project deadline',
                      on: true,
                    },
                    {
                      label: 'Weekly summary',
                      sub: 'Every Monday morning at 9 AM',
                      on: false,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between"
                    >
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {item.label}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {item.sub}
                        </div>
                      </div>
                      <Toggle
                        defaultChecked={item.on}
                        checked={item.controlled ? item.on : undefined}
                        onChange={
                          item.label === 'AI evidence processing updates'
                            ? setAiProcessingNotificationsEnabled
                            : undefined
                        }
                      />
                    </div>
                  ))}
                </div>
              </SectionCard>
            </>
          )}

          {activeTab === 'security' && (
            <>
              <LoginPinSection />
            </>
          )}

          {activeTab === 'ai' && (
            <>
              <SectionCard title="Model Configuration">
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-medium">
                    <label className="text-muted-foreground">
                      Overlap Detection Sensitivity
                    </label>
                    <span className="text-primary font-mono">70%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    defaultValue="70"
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[11px] text-muted-foreground">
                    <span>Less sensitive</span>
                    <span>More sensitive</span>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Minimum AI Confidence (%)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    defaultValue="75"
                    className={inputClass}
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Suggestions below this threshold are suppressed
                  </p>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Automatic Evidence Linking
                  </label>
                  <select className={`${inputClass} cursor-pointer`}>
                    <option value="aggressive">
                      Aggressive — Link all possible matches
                    </option>
                    <option value="balanced">
                      Balanced — Only high confidence
                    </option>
                    <option value="conservative">
                      Conservative — Very likely matches only
                    </option>
                    <option value="manual">
                      Manual — No automatic linking
                    </option>
                  </select>
                </div>
              </SectionCard>

              <SectionCard title="Source Code Analysis">
                <div className="space-y-4">
                  {[
                    'Analyze Git commit history',
                    'Detect code duplication',
                    'Analyze comments and documentation',
                    'Track file changes over time',
                  ].map((label) => (
                    <div
                      key={label}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm text-foreground">{label}</span>
                      <Toggle defaultChecked />
                    </div>
                  ))}
                </div>
              </SectionCard>

              <div className="rounded-lg bg-amber-500/5 border border-amber-500/20 p-4 flex items-start gap-3">
                <span className="text-amber-400 text-sm">⚠</span>
                <p className="text-sm text-muted-foreground">
                  Configuration changes apply to new analyses only. Existing
                  projects will not be re-analyzed automatically.
                </p>
              </div>
            </>
          )}

          {activeTab === 'data' && (
            <>
              <SectionCard title="Student Import Template">
                <p className="text-sm text-muted-foreground mb-4">
                  Download a standardized template for bulk importing students
                  and groups. The template includes columns for Name and Student
                  Number with example data.
                </p>
                <button
                  onClick={handleDownloadTemplate}
                  disabled={templateDownloading}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {templateDownloading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Downloading…
                    </>
                  ) : (
                    <>
                      <Download size={16} />
                      Download Template (Excel)
                    </>
                  )}
                </button>
                {templateError && (
                  <p className="mt-3 text-xs text-red-400">{templateError}</p>
                )}
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs text-muted-foreground">
                    <strong>Instructions:</strong> Download the template, fill
                    in student names and numbers, then upload the file in the
                    Module Management page to add multiple students at once.
                  </p>
                </div>
              </SectionCard>

              <SectionCard title="Rubric Scoring Template">
                <p className="text-sm text-muted-foreground mb-4">
                  Download a standardized rubric template for creating scoring
                  criteria and proficiency levels. The template includes example
                  criteria and can be customized for any assessment.
                </p>
                <button
                  onClick={handleDownloadRubricTemplate}
                  disabled={rubricDownloading}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {rubricDownloading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Downloading…
                    </>
                  ) : (
                    <>
                      <Download size={16} />
                      Download Rubric Template (Excel)
                    </>
                  )}
                </button>
                {rubricError && (
                  <p className="mt-3 text-xs text-red-400">{rubricError}</p>
                )}
                <div className="mt-4 pt-4 border-t border-border">
                  <p className="text-xs text-muted-foreground">
                    <strong>Features:</strong> Includes predefined proficiency
                    levels (Excellent, Good, Fair, Poor), point values for each
                    level, and space for detailed descriptors of student
                    performance.
                  </p>
                </div>
              </SectionCard>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
