'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { EvidenceUploadProvider } from '@/context/EvidenceUploadContext';
import Header from '@/components/layout/Header';
import Breadcrumb from '@/components/layout/Breadcrumb';

export default function AppLayout({ children }) {
  const { user, ready } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (ready && !user) {
      router.replace('/');
    }
  }, [ready, user, router]);

  if (!ready || !user) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <EvidenceUploadProvider>
      <div className="min-h-screen bg-background flex flex-col">
        <Header />
        <Breadcrumb />
        <main className="flex-1">
          <div className="max-w-7xl mx-auto px-8 py-8">{children}</div>
        </main>
      </div>
    </EvidenceUploadProvider>
  );
}
