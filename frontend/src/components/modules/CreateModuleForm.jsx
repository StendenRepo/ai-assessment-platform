'use client';

import { useState } from 'react';
import { apiFetch } from '@/lib/apiFetch';

export default function CreateModuleForm({ onCreated }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);

  function validate() {
    const next = {};
    if (!name.trim()) next.name = 'Module name is required';
    if (!code.trim()) next.code = 'Module code is required';
    return next;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const fieldErrors = validate();
    if (Object.keys(fieldErrors).length) {
      setErrors(fieldErrors);
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      const createdModule = await apiFetch('/modules', {
        method: 'POST',
        json: { name: name.trim(), code: code.trim() },
      });
      setName('');
      setCode('');
      onCreated(createdModule);
    } catch (err) {
      const msg = err.message || '';
      if (msg.toLowerCase().includes('code')) {
        setErrors({ code: 'A module with this code already exists' });
      } else {
        setErrors({ form: msg || 'Something went wrong' });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg bg-card border border-border p-6 space-y-4"
    >
      <h2 className="text-base font-semibold text-foreground">New Module</h2>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Module Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Applied Artificial Intelligence"
            className={`w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 ${
              errors.name ? 'border-red-500' : 'border-border'
            }`}
          />
          {errors.name && <p className="text-xs text-red-400">{errors.name}</p>}
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Module Code
          </label>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="AAI-2026"
            className={`w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 ${
              errors.code ? 'border-red-500' : 'border-border'
            }`}
          />
          {errors.code && <p className="text-xs text-red-400">{errors.code}</p>}
        </div>
      </div>

      {errors.form && <p className="text-xs text-red-400">{errors.form}</p>}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={submitting}
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {submitting ? 'Creating...' : 'Create Module'}
        </button>
      </div>
    </form>
  );
}
