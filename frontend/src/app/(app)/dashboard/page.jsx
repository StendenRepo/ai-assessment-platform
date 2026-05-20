import Breadcrumb from '@/components/layout/Breadcrumb';
import Dashboard from './_components/Dashboard';

export default function DashboardPage() {
  return (
    <>
      <Breadcrumb crumbs={[{ label: 'Dashboard' }]} />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <Dashboard />
      </div>
    </>
  );
}
