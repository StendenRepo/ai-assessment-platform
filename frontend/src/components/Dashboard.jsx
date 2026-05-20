'use client';
import { useRouter } from 'next/navigation';
import { mockProjects } from '@/lib/mockData';
export default function Dashboard() {
  const router = useRouter();
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Dashboard</h2>
        <p className="text-gray-600">Overview of all active group projects</p>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8">
        <div
          className="border-2 border-gray-400 p-6 cursor-pointer hover:border-black transition-all"
          onClick={() => router.push('/projects')}
        >
          <div className="text-4xl font-bold mb-2">12</div>
          <div className="text-sm">Active Projects</div>
        </div>
        <div
          className="border-2 border-gray-400 p-6 cursor-pointer hover:border-black transition-all"
          onClick={() => router.push('/projects')}
        >
          <div className="text-4xl font-bold mb-2">3</div>
          <div className="text-sm">Deadlines This Week</div>
        </div>
      </div>

      <div className="mb-4">
        <h3 className="text-xl font-bold">Recent Projects</h3>
      </div>

      <div className="space-y-4">
        {mockProjects.map((project) => (
          <div
            key={project.id}
            className="border-2 border-gray-400 p-6 hover:border-black cursor-pointer"
            onClick={() => router.push(`/projects/${project.id}`)}
          >
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-4 mb-2">
                  <h4 className="text-lg font-bold">{project.name}</h4>
                  <span className="border border-gray-400 px-3 py-1 text-sm">
                    [
                    {project.status === 'active'
                      ? 'ACTIVE'
                      : project.status.toUpperCase()}
                    ]
                  </span>
                </div>
                <div className="text-sm text-gray-600 space-x-4">
                  <span>{project.course}</span>
                  <span>| Group {project.groupNumber}</span>
                  <span>
                    | Deadline:{' '}
                    {new Date(project.deadline).toLocaleDateString('en-US')}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <div className="flex justify-between mb-2 text-sm">
                <span>Assessment Progress:</span>
                <span className="font-bold">{project.assessmentProgress}%</span>
              </div>
              <div className="w-full h-6 border-2 border-gray-400">
                <div
                  className="h-full bg-gray-400"
                  style={{ width: `${project.assessmentProgress}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
