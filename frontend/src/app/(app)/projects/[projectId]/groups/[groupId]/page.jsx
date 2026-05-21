import Breadcrumb from '@/components/layout/Breadcrumb';
import ProjectDetail from './_components/ProjectDetail';

export default async function ProjectDetailPage({ params }) {
  const { projectId, groupId } = await params;
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Projects', href: '/projects' },
          { label: 'Groups', href: `/projects/${projectId}` },
          { label: 'Project Detail' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <ProjectDetail projectId={projectId} groupId={groupId} />
      </div>
    </>
  );
}
