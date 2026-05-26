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

export async function apiLogin(email, password) {
  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Login failed');
  }

  const { access_token } = await res.json();

  const meRes = await fetch(`${API_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });

  if (!meRes.ok) throw new Error('Failed to fetch user info');
  const user = await meRes.json();

  saveSession(access_token, user);
  return user;
}

export function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
