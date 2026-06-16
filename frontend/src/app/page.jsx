'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GraduationCap, Shield } from 'lucide-react';
import { apiLogin, clearSession } from '@/lib/auth';
import { useAuth } from '@/context/AuthContext';
import { APP_PATHS } from '@/lib/routes';

export default function RootPage() {
  const router = useRouter();
  const { user, ready, login } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [pinRequired, setPinRequired] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (ready && user) {
      router.replace(
        isAdmin && user.is_admin ? APP_PATHS.admin : APP_PATHS.dashboard
      );
    }
  }, [ready, user, router, isAdmin]);

  const handleModeSwitch = (adminMode) => {
    setIsAdmin(adminMode);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await apiLogin(
        email,
        password,
        pinRequired ? pin : undefined
      );
      if (result.pinRequired) {
        setPinRequired(true);
        return;
      }
      if (isAdmin && !result.is_admin) {
        clearSession();
        setError('This account does not have administrator access.');
        return;
      }
      login(result);
      // navigation is handled by the useEffect above
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!ready || (ready && user)) return null;

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-8">
      <div className="w-full max-w-sm space-y-7">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
            <GraduationCap size={18} className="text-primary-foreground" />
          </div>
          <span className="text-lg font-semibold text-foreground">
            AssessAI
          </span>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-foreground">Welcome back</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Sign in to your account to continue
          </p>
        </div>

        <div className="flex rounded-lg bg-secondary border border-border p-1 gap-1">
          <button
            type="button"
            onClick={() => handleModeSwitch(false)}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
              !isAdmin
                ? 'bg-background text-foreground shadow-sm border border-border'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Teacher
          </button>
          <button
            type="button"
            onClick={() => handleModeSwitch(true)}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
              isAdmin
                ? 'bg-background text-foreground shadow-sm border border-border'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Administrator
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              Email address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={
                isAdmin ? 'Admin@nhlstenden.com' : 'Teacher@nhlstenden.com'
              }
              required
              className="w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit(e)}
              placeholder="••••••••"
              required
              className="w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
            />
          </div>

          {pinRequired && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">PIN</label>
              <input
                type="password"
                inputMode="numeric"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit(e)}
                placeholder="••••"
                autoFocus
                required
                className="w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
              />
              <p className="text-xs text-muted-foreground">
                This account is protected by a PIN. Enter it to continue.
              </p>
            </div>
          )}

          {error && (
            <p className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 rounded-md px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-primary-foreground rounded-md py-2.5 text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading
              ? 'Signing in…'
              : `Sign in as ${isAdmin ? 'Administrator' : 'Teacher'}`}
          </button>
        </form>

        <div className="flex items-start gap-2.5 rounded-lg bg-secondary border border-border p-3">
          <Shield size={13} className="text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            All data is processed on-premises and encrypted. Fully compliant
            with GDPR regulations.
          </p>
        </div>
      </div>
    </div>
  );
}
