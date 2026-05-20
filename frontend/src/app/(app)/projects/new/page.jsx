import Breadcrumb from '@/components/Breadcrumb';
import ProjectSetup from '@/components/ProjectSetup';

export default function NewProjectPage() {
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Projects', href: '/projects' },
          { label: 'New Project' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <ProjectSetup />
      </div>
    </>
  );
}
