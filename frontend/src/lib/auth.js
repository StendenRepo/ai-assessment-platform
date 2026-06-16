import { API_PATHS } from '@/lib/routes';

const TOKEN_KEY = 'assessai_token';
const USER_KEY = 'assessai_user';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function errorMessage(data, fallback) {
  if (typeof data?.detail === 'string') return data.detail;
  return fallback;
}

export async function apiLogin(email, password, pin) {
  const res = await fetch(`${API_URL}/api/v1${API_PATHS.authLogin}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, ...(pin ? { pin } : {}) }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(errorMessage(data, 'Login failed'));
  }

  const data = await res.json();
  if (data.pin_required) {
    return { pinRequired: true };
  }

  const access_token = data.access_token;
  const meRes = await fetch(`${API_URL}/api/v1${API_PATHS.authMe}`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });

  if (!meRes.ok) throw new Error('Failed to fetch user info');
  const user = await meRes.json();

  saveSession(access_token, user);
  return user;
}

export async function setPin(password, pin) {
  const res = await fetch(`${API_URL}/api/v1${API_PATHS.authPin}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ password, pin }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(errorMessage(data, 'Failed to set PIN'));
  }
  return res.json();
}

export async function removePin(password) {
  const res = await fetch(`${API_URL}/api/v1${API_PATHS.authPin}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(errorMessage(data, 'Failed to remove PIN'));
  }
  return res.json();
}

export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
