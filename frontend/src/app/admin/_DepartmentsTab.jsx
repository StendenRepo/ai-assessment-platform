'use client';

import { useCallback, useEffect, useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
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

export function DepartmentsTab({ onDataChange }) {
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState({ name: '' });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  const fetchDepartments = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const data = await adminFetch('/departments');
      setDepartments(data);
      onDataChange?.(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [onDataChange]);

  useEffect(() => {
    fetchDepartments();
  }, [fetchDepartments]);

  const openCreate = () => {
    setForm({ name: '' });
    setFormError('');
    setModal({ mode: 'create' });
  };

  const openEdit = (d) => {
    setForm({ name: d.name });
    setFormError('');
    setModal({ mode: 'edit', data: d });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      if (modal.mode === 'create') {
        await adminFetch('/departments', {
          method: 'POST',
          body: JSON.stringify(form),
        });
      } else {
        await adminFetch(`/departments/${modal.data.id}`, {
          method: 'PUT',
          body: JSON.stringify(form),
        });
      }
      setModal(null);
      fetchDepartments();
    } catch (e) {
      setFormError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await adminFetch(`/departments/${deleteTarget.id}`, { method: 'DELETE' });
      setDeleteTarget(null);
      fetchDepartments();
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
          {departments.length} department{departments.length !== 1 ? 's' : ''}
        </p>
        <button
          onClick={openCreate}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
        >
          + Add Department
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
                Teachers
              </th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                Created
              </th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {departments.length === 0 ? (
              <tr>
                <td
                  colSpan={4}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No departments yet.
                </td>
              </tr>
            ) : (
              departments.map((d) => (
                <tr
                  key={d.id}
                  className="hover:bg-secondary/50 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-foreground">
                    {d.name}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {d.teacher_count}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        onClick={() => openEdit(d)}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                      >
                        <Pencil size={13} />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(d)}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 size={13} />
                      </button>
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
          title={modal.mode === 'create' ? 'Add Department' : 'Edit Department'}
          onClose={() => setModal(null)}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <Field label="Department name">
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ name: e.target.value })}
                placeholder="e.g. Computer Science"
                required
                autoFocus
                className={inputCls}
              />
            </Field>
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
