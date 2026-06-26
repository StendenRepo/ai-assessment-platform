'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { GraduationCap, Shield, ChevronDown, Search } from 'lucide-react';
import { apiLogin, apiGetLoginUsers, clearSession } from '@/lib/auth';
import { useAuth } from '@/context/AuthContext';
import { APP_PATHS } from '@/lib/routes';

export default function RootPage() {
  const router = useRouter();
  const { user, ready, login } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [pinRequired, setPinRequired] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const dropdownRef = useRef(null);
  const passwordRef = useRef(null);

  useEffect(() => {
    if (ready && user) {
      router.replace(
        isAdmin && user.is_admin ? APP_PATHS.admin : APP_PATHS.dashboard
      );
    }
  }, [ready, user, router, isAdmin]);

  useEffect(() => {
    setUsersLoading(true);
    setSelectedUser(null);
    setSearchQuery('');
    setError('');
    apiGetLoginUsers(isAdmin)
      .then(setUsers)
      .catch(() => setUsers([]))
      .finally(() => setUsersLoading(false));
  }, [isAdmin]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleModeSwitch = (adminMode) => {
    setIsAdmin(adminMode);
    setPassword('');
    setPin('');
    setPinRequired(false);
    setError('');
  };

  const handleSelectUser = (u) => {
    setSelectedUser(u);
    setSearchQuery(u.name);
    setDropdownOpen(false);
    setPin('');
    setPinRequired(false);
    setError('');
    setTimeout(() => passwordRef.current?.focus(), 50);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedUser) {
      setError('Please select your name from the list.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const result = await apiLogin(
        selectedUser.email,
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
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const filteredUsers = users.filter(
    (u) =>
      u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
          <div className="space-y-1.5" ref={dropdownRef}>
            <label className="text-sm font-medium text-foreground">
              {isAdmin ? 'Administrator' : 'Teacher'}
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setDropdownOpen((o) => !o);
                  setHighlightedIndex(0);
                }}
                className={`w-full bg-secondary border rounded-md px-3 py-2.5 text-sm text-left flex items-center justify-between transition-all focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent ${
                  selectedUser
                    ? 'border-border text-foreground'
                    : 'border-border text-muted-foreground'
                }`}
              >
                <span className="truncate">
                  {selectedUser
                    ? selectedUser.name
                    : usersLoading
                      ? 'Loading…'
                      : `Select ${isAdmin ? 'administrator' : 'teacher'}…`}
                </span>
                <ChevronDown
                  size={14}
                  className={`shrink-0 ml-2 text-muted-foreground transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
                />
              </button>

              {dropdownOpen && (
                <div className="absolute z-20 w-full mt-1 bg-background border border-border rounded-md shadow-lg overflow-hidden">
                  <div className="p-2 border-b border-border">
                    <div className="flex items-center gap-2 bg-secondary rounded-md px-2.5 py-1.5">
                      <Search
                        size={13}
                        className="text-muted-foreground shrink-0"
                      />
                      <input
                        autoFocus
                        type="text"
                        value={searchQuery}
                        onChange={(e) => {
                          setSearchQuery(e.target.value);
                          setHighlightedIndex(0);
                          if (
                            selectedUser &&
                            e.target.value !== selectedUser.name
                          ) {
                            setSelectedUser(null);
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && filteredUsers.length > 0) {
                            handleSelectUser(filteredUsers[highlightedIndex]);
                          } else if (e.key === 'ArrowDown') {
                            setHighlightedIndex((i) =>
                              Math.min(i + 1, filteredUsers.length - 1)
                            );
                          } else if (e.key === 'ArrowUp') {
                            setHighlightedIndex((i) => Math.max(i - 1, 0));
                          }
                        }}
                        placeholder="Search by name…"
                        className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                      />
                    </div>
                  </div>
                  <ul className="max-h-48 overflow-y-auto py-1">
                    {filteredUsers.length === 0 ? (
                      <li className="px-3 py-2 text-sm text-muted-foreground">
                        No results found
                      </li>
                    ) : (
                      filteredUsers.map((u, index) => (
                        <li key={u.id}>
                          <button
                            type="button"
                            onClick={() => handleSelectUser(u)}
                            className={`w-full text-left px-3 py-2 text-sm hover:bg-secondary transition-colors ${
                              index === highlightedIndex
                                ? 'bg-secondary text-foreground font-medium'
                                : 'text-foreground'
                            }`}
                          >
                            <span className="block">{u.name}</span>
                            <span className="block text-xs text-muted-foreground">
                              {u.email}
                            </span>
                          </button>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">
              Password
            </label>
            <input
              ref={passwordRef}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit(e)}
              placeholder="••••••••••••"
              required
              disabled={!selectedUser}
              className="w-full bg-secondary border border-border rounded-md px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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
            disabled={loading || !selectedUser || !password}
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
