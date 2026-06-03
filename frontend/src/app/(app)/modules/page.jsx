'use client';

import { useEffect, useState } from 'react';
import { BookOpen } from 'lucide-react';
import { apiFetch } from '@/lib/apiFetch';
import CreateModuleForm from '@/components/modules/CreateModuleForm';

const statusClasses = {
  active: 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20',
  archived: 'bg-secondary text-muted-foreground ring-1 ring-border',
};

export default function ModulesPage() {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiFetch('/modules')
      .then(setModules)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  function handleCreated(newModule) {
    setModules((prev) => [newModule, ...prev]);
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Modules</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Create and manage your course modules
        </p>
      </div>

      <CreateModuleForm onCreated={handleCreated} />

      <div>
        <h2 className="text-base font-semibold text-foreground mb-4">
          All Modules
        </h2>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {!loading && !error && modules.length === 0 && (
          <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
            <BookOpen
              size={32}
              className="mx-auto mb-3 text-muted-foreground/50"
            />
            <p className="text-sm text-muted-foreground">
              No modules yet. Create your first one above.
            </p>
          </div>
        )}

        {modules.length > 0 && (
          <div className="rounded-lg bg-card border border-border divide-y divide-border overflow-hidden">
            {modules.map((mod) => (
              <div key={mod.id} className="flex items-center gap-6 px-6 py-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <span className="text-sm font-semibold text-foreground">
                      {mod.name}
                    </span>
                    <span className="text-xs font-mono text-muted-foreground bg-secondary px-2 py-0.5 rounded">
                      {mod.code}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        statusClasses[mod.status] ?? statusClasses.active
                      }`}
                    >
                      {mod.status}
                    </span>
                  </div>
                  {mod.academic_year && (
                    <p className="text-xs text-muted-foreground">
                      {mod.academic_year}
                    </p>
                  )}
                </div>
                <span className="text-xs text-muted-foreground shrink-0">
                  {new Date(mod.created_at).toLocaleDateString('en-GB', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
