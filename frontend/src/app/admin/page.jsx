'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, ClipboardList, Settings, Users } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { NotificationProvider } from '@/context/NotificationContext';
import Header from '@/components/layout/Header';
import { adminFetch } from '@/lib/api/adminFetch';
import { APP_PATHS } from '@/lib/routes';
import { TabBtn } from './_ui';
import { TeachersTab } from './_TeachersTab';
import { DepartmentsTab } from './_DepartmentsTab';
import { SettingsTab } from './_SettingsTab';
import { AuditTab } from './_AuditTab';

export default function AdminPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState('teachers');
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      router.replace(APP_PATHS.root);
      return;
    }
    if (!user.is_admin) {
      router.replace(APP_PATHS.dashboard);
    }
  }, [ready, user, router]);

  useEffect(() => {
    if (!ready || !user?.is_admin) return;
    adminFetch('/departments')
      .then((data) => setDepartments(data))
      .catch(() => {});
  }, [ready, user]);

  if (!ready || !user || !user.is_admin) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <NotificationProvider>
      <div className="min-h-screen bg-background">
        <Header
          navItems={[]}
          subtitle="Admin Panel"
          logoHref={APP_PATHS.admin}
        />

        <main className="max-w-7xl mx-auto px-8 py-8">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-foreground">Admin Panel</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage teachers, departments, and audit logs
            </p>
          </div>

          <div className="flex border-b border-border mb-6">
            <TabBtn
              active={tab === 'teachers'}
              onClick={() => setTab('teachers')}
              icon={<Users size={14} />}
              label="Teachers"
            />
            <TabBtn
              active={tab === 'departments'}
              onClick={() => setTab('departments')}
              icon={<Building2 size={14} />}
              label="Departments"
            />
            <TabBtn
              active={tab === 'audit'}
              onClick={() => setTab('audit')}
              icon={<ClipboardList size={14} />}
              label="Audit Logs"
            />
            <div className="flex-1" />
            <TabBtn
              active={tab === 'settings'}
              onClick={() => setTab('settings')}
              icon={<Settings size={14} />}
              label="Settings"
            />
          </div>

          {tab === 'teachers' && (
            <TeachersTab departments={departments} currentUserId={user.id} />
          )}
          {tab === 'departments' && (
            <DepartmentsTab onDataChange={setDepartments} />
          )}
          {tab === 'audit' && <AuditTab />}
          {tab === 'settings' && <SettingsTab />}
        </main>
      </div>
    </NotificationProvider>
  );
}
