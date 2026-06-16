'use client';

import { useState } from 'react';
import {
  User,
  Brain,
  Shield,
  Plug,
  CheckCircle,
  XCircle,
  Sun,
  Moon,
  Loader2,
} from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';
import { useNotifications } from '@/context/NotificationContext';
import { useAuth } from '@/context/AuthContext';
import { setPin as apiSetPin, removePin as apiRemovePin } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const tabs = [
  { key: 'general', label: 'General', icon: User },
  { key: 'ai', label: 'AI Configuration', icon: Brain },
  { key: 'privacy', label: 'Privacy & GDPR', icon: Shield },
  { key: 'integration', label: 'Integrations', icon: Plug },
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
            {loading ? 'Removing…' : 'Remove PIN'}
          </button>
        ) : (
          <button
            onClick={handleSet}
            disabled={loading || !password || !pin}
            className="px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading ? 'Saving…' : 'Set PIN'}
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
  const [integrationTestState, setIntegrationTestState] = useState({});

  const connectedServices = [
    {
      id: 'ollama',
      name: 'Ollama',
      desc: 'Local LLM runtime for analysis and generation',
      active: true,
      detail: 'Configured via backend OLLAMA_BASE_URL',
      canTest: true,
    },
    {
      id: 'smtp',
      name: 'Email Server (SMTP)',
      desc: 'Send notifications and report exports',
      active: true,
      detail: 'smtp.university.edu:587',
      canTest: false,
    },
  ];

  const testOllamaConnection = async () => {
    setIntegrationTestState((prev) => ({
      ...prev,
      ollama: { status: 'loading', message: 'Testing connection...' },
    }));

    try {
      const res = await fetch(`${API_URL}/api/v1/health/ollama`);
      const data = await res.json().catch(() => ({}));

      if (!res.ok || !data.reachable) {
        throw new Error(data.detail || `Connection failed (${res.status})`);
      }

      const modelInfo =
        data.model_count > 0
          ? `${data.model_count} model(s) detected`
          : 'Connected but no models found';

      setIntegrationTestState((prev) => ({
        ...prev,
        ollama: {
          status: 'success',
          message: `Connected to ${data.base_url}. ${modelInfo}.`,
        },
      }));
    } catch (err) {
      setIntegrationTestState((prev) => ({
        ...prev,
        ollama: {
          status: 'error',
          message: err?.message || 'Connection test failed',
        },
      }));
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

          {activeTab === 'privacy' && (
            <>
              <SectionCard title="Data Storage">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Data Retention Period
                  </label>
                  <select className={`${inputClass} cursor-pointer`}>
                    <option>30 days after project completion</option>
                    <option>90 days after project completion</option>
                    <option>180 days after project completion</option>
                    <option>1 year after project completion</option>
                    <option>Unlimited (manual deletion)</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Automatic Anonymization
                  </label>
                  <select className={`${inputClass} cursor-pointer`}>
                    <option>Never</option>
                    <option>After 30 days</option>
                    <option>After 90 days</option>
                    <option>After 180 days</option>
                  </select>
                </div>
              </SectionCard>

              <SectionCard title="GDPR Compliance">
                <div className="space-y-4">
                  {[
                    {
                      label: 'Log all data access',
                      sub: 'Required by GDPR — cannot be disabled',
                      on: true,
                      locked: true,
                    },
                    {
                      label: 'Require student consent for analysis',
                      sub: 'Students must agree before AI analysis',
                      on: true,
                      locked: false,
                    },
                    {
                      label: 'Anonymize data in exports',
                      sub: 'Replace names with pseudonyms',
                      on: false,
                      locked: false,
                    },
                    {
                      label: 'Store audit trail for 7 years',
                      sub: 'Required for institutional compliance',
                      on: true,
                      locked: true,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex items-start justify-between gap-4"
                    >
                      <div>
                        <div className="text-sm font-medium text-foreground flex items-center gap-2">
                          {item.label}
                          {item.locked && (
                            <span className="text-[10px] rounded-full px-2 py-0.5 bg-secondary text-muted-foreground ring-1 ring-border">
                              Required
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {item.sub}
                        </div>
                      </div>
                      <Toggle defaultChecked={item.on} disabled={item.locked} />
                    </div>
                  ))}
                </div>
                <div className="pt-2 border-t border-border">
                  <button className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                    Download GDPR Compliance Report
                  </button>
                </div>
              </SectionCard>

              <SectionCard title="Data Deletion">
                <p className="text-sm text-muted-foreground">
                  Students have the right to request deletion of their personal
                  data under GDPR.
                </p>
                <div className="flex gap-2">
                  <button className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                    Process Deletion Request
                  </button>
                  <button className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                    Run Automatic Cleanup
                  </button>
                </div>
              </SectionCard>
            </>
          )}

          {activeTab === 'integration' && (
            <>
              <SectionCard title="Connected Services">
                {connectedServices.map((svc) => (
                  <div
                    key={svc.name}
                    className="rounded-lg border border-border p-4 space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-sm font-semibold text-foreground">
                          {svc.name}
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {svc.desc}
                        </div>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium shrink-0 ${svc.active ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20' : 'bg-secondary text-muted-foreground ring-1 ring-border'}`}
                      >
                        {svc.active ? (
                          <CheckCircle size={11} />
                        ) : (
                          <XCircle size={11} />
                        )}
                        {svc.active ? 'Active' : 'Not Active'}
                      </span>
                    </div>
                    <div className="text-xs font-mono text-muted-foreground">
                      {svc.detail}
                    </div>
                    {svc.id === 'ollama' && integrationTestState.ollama && (
                      <div
                        className={`text-xs rounded-md px-2.5 py-2 ${integrationTestState.ollama.status === 'success' ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20' : integrationTestState.ollama.status === 'error' ? 'bg-red-500/10 text-red-400 ring-1 ring-red-500/20' : 'bg-secondary text-muted-foreground ring-1 ring-border'}`}
                      >
                        {integrationTestState.ollama.message}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <button className="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                        Configure
                      </button>
                      {svc.active && svc.canTest && (
                        <button
                          onClick={testOllamaConnection}
                          disabled={
                            integrationTestState.ollama?.status === 'loading'
                          }
                          className="px-3 py-1.5 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
                        >
                          {integrationTestState.ollama?.status ===
                            'loading' && (
                            <Loader2 size={12} className="animate-spin" />
                          )}
                          Test Connection
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </SectionCard>

              <SectionCard title="API Access">
                <p className="text-sm text-muted-foreground">
                  Generate API keys for external integrations and custom
                  tooling.
                </p>
                <div className="rounded-lg bg-secondary border border-border p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold text-foreground">
                      Production API Key
                    </span>
                    <span className="text-[10px] rounded-full px-2.5 py-0.5 bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20">
                      Active
                    </span>
                  </div>
                  <div className="font-mono text-xs text-muted-foreground bg-background border border-border rounded-md px-3 py-2">
                    api_prod_************************************************
                  </div>
                </div>
                <button className="px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all">
                  + Generate New API Key
                </button>
              </SectionCard>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
