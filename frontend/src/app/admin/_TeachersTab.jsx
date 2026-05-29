'use client';

import { useCallback, useEffect, useState } from 'react';
import { Pencil, Shield, Trash2 } from 'lucide-react';
import { adminFetch } from '@/lib/adminFetch';
import {
  DeleteConfirm,
  Field,
  FormError,
  Modal,
  SaveButtons,
  Spinner,
  inputCls,
} from './_ui';

const TEACHER_DEFAULT = {
  name: '',
  email: '',
  password: '',
  department_id: '',
  is_admin: false,
};

export function TeachersTab({ departments, currentUserId }) {
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(TEACHER_DEFAULT);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const fetchTeachers = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setTeachers(await adminFetch('/teachers'));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTeachers();
  }, [fetchTeachers]);

  const openCreate = () => {
    setForm(TEACHER_DEFAULT);
    setFormError('');
    setModal({ mode: 'create' });
  };

  const openEdit = (t) => {
    setForm({
      name: t.name,
      email: t.email,
      password: '',
      department_id: t.department_id ?? '',
      is_admin: t.is_admin,
    });
    setFormError('');
    setModal({ mode: 'edit', data: t });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      const payload = {
        name: form.name,
        email: form.email,
        department_id: form.department_id || null,
        is_admin: form.is_admin,
        ...(form.password ? { password: form.password } : {}),
      };
      if (modal.mode === 'create') {
        if (!form.password) {
          setFormError('Password is required');
          return;
        }
        await adminFetch('/teachers', {
          method: 'POST',
          body: JSON.stringify({ ...payload, password: form.password }),
        });
      } else {
        await adminFetch(`/teachers/${modal.data.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
      setModal(null);
      fetchTeachers();
    } catch (e) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await adminFetch(`/teachers/${deleteTarget.id}`, { method: 'DELETE' });
      setDeleteTarget(null);
      fetchTeachers();
    } catch (e) {
      setError(e.message);
      setDeleteTarget(null);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-500 py-4">{error}</p>;

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-muted-foreground">
          {teachers.length} teacher{teachers.length !== 1 ? 's' : ''}
        </p>
        <button
          onClick={openCreate}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
        >
          + Add Teacher
        </button>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-secondary">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Name
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Email
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Department
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Role
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Created
              </th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {teachers.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No teachers yet.
                </td>
              </tr>
            ) : (
              teachers.map((t) => (
                <tr
                  key={t.id}
                  className="hover:bg-secondary/50 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-foreground">
                    {t.name}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{t.email}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {t.department_name ?? (
                      <span className="text-muted-foreground/40">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {t.is_admin ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                        <Shield size={10} /> Admin
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Teacher
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => openEdit(t)}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                      >
                        <Pencil size={13} />
                      </button>
                      {!t.is_protected && t.id !== currentUserId && (
                        <button
                          onClick={() => setDeleteTarget(t)}
                          className="p-1.5 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Add Teacher' : 'Edit Teacher'}
          onClose={() => setModal(null)}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Full name">
              <input
                type="text"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
                placeholder="Jane Smith"
                required
                className={inputCls}
              />
            </Field>
            <Field label="Email">
              <input
                type="email"
                value={form.email}
                onChange={(e) =>
                  setForm((f) => ({ ...f, email: e.target.value }))
                }
                placeholder="jane@nhlstenden.com"
                required
                className={inputCls}
              />
            </Field>
            <Field
              label={
                modal.mode === 'edit'
                  ? 'New password (leave blank to keep)'
                  : 'Password'
              }
            >
              <input
                type="password"
                value={form.password}
                onChange={(e) =>
                  setForm((f) => ({ ...f, password: e.target.value }))
                }
                placeholder="••••••••"
                {...(modal.mode === 'create' ? { required: true } : {})}
                className={inputCls}
              />
            </Field>
            <Field label="Department">
              <select
                value={form.department_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, department_id: e.target.value }))
                }
                className={inputCls}
              >
                <option value="">— No department —</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>
            <label className="flex items-center gap-2.5 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={form.is_admin}
                onChange={(e) =>
                  setForm((f) => ({ ...f, is_admin: e.target.checked }))
                }
                className="w-4 h-4 accent-primary"
              />
              <span className="text-sm text-foreground">
                Administrator access
              </span>
            </label>
            <FormError message={formError} />
            <SaveButtons onCancel={() => setModal(null)} saving={saving} />
          </form>
        </Modal>
      )}

      {deleteTarget && (
        <DeleteConfirm
          label={deleteTarget.name}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
