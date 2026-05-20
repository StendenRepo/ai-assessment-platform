import Breadcrumb from '@/components/Breadcrumb';
import CriteriaSetup from '@/components/CriteriaSetup';

export default async function CriteriaPage({ params }) {
  const { projectId } = await params;
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Projects', href: '/projects' },
          { label: 'New Project', href: '/projects/new' },
          { label: 'Setup Criteria & Rubrics' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <CriteriaSetup projectId={projectId} />
      </div>
    </>
  );
}
