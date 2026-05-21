import Breadcrumb from '@/components/layout/Breadcrumb';
import CriteriaSetup from './_components/CriteriaSetup';

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
