'use client';
import { useRouter } from 'next/navigation';
const groups = [
    { id: 'group-1', name: 'Group 1', class: 'CS401-A', members: 4, assessmentProgress: 75, evidenceCount: 12 },
    { id: 'group-2', name: 'Group 2', class: 'CS401-A', members: 5, assessmentProgress: 40, evidenceCount: 8 },
    { id: 'group-3', name: 'Group 3', class: 'CS401-B', members: 4, assessmentProgress: 90, evidenceCount: 15 },
    { id: 'group-4', name: 'Group 4', class: 'CS401-B', members: 3, assessmentProgress: 25, evidenceCount: 5 },
];
export default function GroupsList({ projectId }) {
    const router = useRouter();
    return (<div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Project Groups</h2>
        <p className="text-gray-600">Select a group to view project details and assess students</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {groups.map((group) => (<div key={group.id} className="border-2 border-gray-400 p-6 hover:border-black cursor-pointer transition-all" onClick={() => router.push(`/projects/${projectId}/groups/${group.id}`)}>
            <div className="mb-4">
              <h3 className="text-xl font-bold mb-2">{group.name}</h3>
              <div className="text-sm text-gray-600 space-x-4">
                <span>Class: {group.class}</span>
                <span>| {group.members} members</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <div className="flex justify-between mb-1 text-sm">
                  <span>Assessment Progress</span>
                  <span className="font-bold">{group.assessmentProgress}%</span>
                </div>
                <div className="w-full h-4 border-2 border-gray-400">
                  <div className="h-full bg-gray-400" style={{ width: `${group.assessmentProgress}%` }}/>
                </div>
              </div>

              <div className="border-t-2 border-gray-300 pt-3">
                <div className="text-sm text-gray-600">
                  Evidence files: <span className="font-bold text-gray-900">{group.evidenceCount}</span>
                </div>
              </div>
            </div>
          </div>))}
      </div>
    </div>);
}
