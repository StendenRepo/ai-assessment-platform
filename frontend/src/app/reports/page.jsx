import Breadcrumb from '@/components/Breadcrumb';
import Reports from '@/components/Reports';
export default function ReportsPage() {
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Reports' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <Reports />
      </div>
    </>
  );
}
