import Breadcrumb from '@/components/layout/Breadcrumb';
import ProjectSetup from './_components/ProjectSetup';

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
