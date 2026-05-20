import Breadcrumb from '@/components/layout/Breadcrumb';
import Settings from './_components/Settings';

export default function SettingsPage() {
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Settings' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <Settings />
      </div>
    </>
  );
}
