'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { mockProjects } from '@/lib/mockData';
export default function ProjectsList() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [courseFilter, setCourseFilter] = useState('all');
  const filteredProjects = mockProjects.filter((project) => {
    const matchesSearch =
      project.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      project.course.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' || project.status === statusFilter;
    const matchesCourse =
      courseFilter === 'all' || project.course === courseFilter;
    return matchesSearch && matchesStatus && matchesCourse;
  });
  const courses = Array.from(new Set(mockProjects.map((p) => p.course)));
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">All Projects</h2>
        <p className="text-gray-600">Browse and search all projects</p>
      </div>

      <div className="border-2 border-gray-400 p-6 mb-6">
        <div className="grid grid-cols-4 gap-4">
          <div className="col-span-2">
            <label className="block font-bold mb-2">Search</label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full border-2 border-gray-400 px-4 py-2"
              placeholder="Search by project name or course..."
            />
          </div>

          <div>
            <label className="block font-bold mb-2">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full border-2 border-gray-400 px-4 py-2"
            >
              <option value="all">All Statuses</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="overdue">Overdue</option>
            </select>
          </div>

          <div>
            <label className="block font-bold mb-2">Course</label>
            <select
              value={courseFilter}
              onChange={(e) => setCourseFilter(e.target.value)}
              className="w-full border-2 border-gray-400 px-4 py-2"
            >
              <option value="all">All Courses</option>
              {courses.map((course) => (
                <option key={course} value={course}>
                  {course}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 text-sm text-gray-600">
          Showing {filteredProjects.length} of {mockProjects.length} projects
        </div>
      </div>

      <div className="space-y-4">
        {filteredProjects.length === 0 ? (
          <div className="border-2 border-gray-400 p-12 text-center text-gray-600">
            <div className="text-4xl mb-4">🔍</div>
            <div>No projects found</div>
            <div className="text-sm mt-2">
              Try adjusting your filters or search term
            </div>
          </div>
        ) : (
          filteredProjects.map((project) => (
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
                  <span className="font-bold">
                    {project.assessmentProgress}%
                  </span>
                </div>
                <div className="w-full h-6 border-2 border-gray-400">
                  <div
                    className="h-full bg-gray-400"
                    style={{ width: `${project.assessmentProgress}%` }}
                  />
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
