import Header from '@/components/layout/Header';
import Breadcrumb from '@/components/layout/Breadcrumb';

export default function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <Breadcrumb />
      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
