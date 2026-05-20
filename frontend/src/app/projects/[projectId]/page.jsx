import Breadcrumb from '@/components/Breadcrumb';
import GroupsList from '@/components/GroupsList';
export default function GroupsPage({ params }) {
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Projects', href: '/projects' },
          { label: 'Groups' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <GroupsList projectId={params.projectId} />
      </div>
    </>
  );
}
