import Breadcrumb from '@/components/Breadcrumb';
import ProjectsList from '@/components/ProjectsList';
export default function ProjectsPage() {
    return (<>
      <Breadcrumb crumbs={[{ label: 'Dashboard', href: '/dashboard' }, { label: 'Projects' }]}/>
      <div className="max-w-7xl mx-auto px-8 py-8">
        <ProjectsList />
      </div>
    </>);
}
