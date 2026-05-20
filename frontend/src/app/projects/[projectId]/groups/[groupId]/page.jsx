import Breadcrumb from '@/components/Breadcrumb';
import ProjectDetail from '@/components/ProjectDetail';
export default function ProjectDetailPage({ params }) {
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Projects', href: '/projects' },
          { label: 'Groups', href: `/projects/${params.projectId}` },
          { label: 'Project Detail' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <ProjectDetail projectId={params.projectId} groupId={params.groupId} />
      </div>
    </>
  );
}
