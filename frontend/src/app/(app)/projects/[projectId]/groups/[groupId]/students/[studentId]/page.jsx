import Breadcrumb from '@/components/Breadcrumb';
import StudentAssessment from '@/components/StudentAssessment';

export default async function StudentAssessmentPage({ params }) {
  const { projectId, groupId, studentId } = await params;
  return (
    <>
      <Breadcrumb
        crumbs={[
          { label: 'Dashboard', href: '/dashboard' },
          { label: 'Projects', href: '/projects' },
          { label: 'Groups', href: `/projects/${projectId}` },
          {
            label: 'Project Detail',
            href: `/projects/${projectId}/groups/${groupId}`,
          },
          { label: 'Student Assessment' },
        ]}
      />
      <div className="max-w-7xl mx-auto px-8 py-8">
        <StudentAssessment
          studentId={studentId}
          projectId={projectId}
          groupId={groupId}
        />
      </div>
    </>
  );
}
