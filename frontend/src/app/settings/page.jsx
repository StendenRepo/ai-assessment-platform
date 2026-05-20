import Breadcrumb from '@/components/Breadcrumb';
import Settings from '@/components/Settings';
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
