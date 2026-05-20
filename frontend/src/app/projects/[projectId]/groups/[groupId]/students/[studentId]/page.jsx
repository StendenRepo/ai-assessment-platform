import Breadcrumb from '@/components/Breadcrumb';
import StudentAssessment from '@/components/StudentAssessment';
export default function StudentAssessmentPage({ params, }) {
    return (<>
      <Breadcrumb crumbs={[
            { label: 'Dashboard', href: '/dashboard' },
            { label: 'Projects', href: '/projects' },
            { label: 'Groups', href: `/projects/${params.projectId}` },
            {
                label: 'Project Detail',
                href: `/projects/${params.projectId}/groups/${params.groupId}`,
            },
            { label: 'Student Assessment' },
        ]}/>
      <div className="max-w-7xl mx-auto px-8 py-8">
        <StudentAssessment studentId={params.studentId} projectId={params.projectId} groupId={params.groupId}/>
      </div>
    </>);
}
