import Header from '@/components/layout/Header';

export default function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main>{children}</main>
    </div>
  );
}
