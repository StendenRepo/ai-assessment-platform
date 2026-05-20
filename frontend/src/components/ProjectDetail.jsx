'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { mockStudents } from '@/lib/mockData';
const evidenceFiles = [
    { id: '1', name: 'auth.tsx', type: 'Code', uploadedBy: 'Lisa Anderson', date: '2026-05-10' },
    { id: '2', name: 'API-docs.md', type: 'Documentation', uploadedBy: 'Thomas Johnson', date: '2026-05-12' },
    { id: '3', name: 'demo-slides.pdf', type: 'Presentation', uploadedBy: 'Maya Patel', date: '2026-05-14' },
    { id: '4', name: 'database-schema.sql', type: 'Code', uploadedBy: 'Mark Davis', date: '2026-05-11' },
];
export default function ProjectDetail({ projectId, groupId, }) {
    const router = useRouter();
    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [dragActive, setDragActive] = useState(false);
    const group = {
        id: groupId,
        name: 'Group 1',
        class: 'CS401-A',
        projectName: 'E-Commerce Platform',
        course: 'Advanced Web Development',
        deadline: '2026-06-15',
    };
    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover')
            setDragActive(true);
        else if (e.type === 'dragleave')
            setDragActive(false);
    };
    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            setUploadedFiles([...uploadedFiles, ...Array.from(e.dataTransfer.files)]);
        }
    };
    const handleFileInput = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            setUploadedFiles([...uploadedFiles, ...Array.from(e.target.files)]);
        }
    };
    return (<div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">
          {group.name} - {group.projectName}
        </h2>
        <p className="text-gray-600">
          {group.course} • Class {group.class}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-8">
        <div className="col-span-2 space-y-6">
          <div className="border-2 border-gray-400 p-6">
            <h3 className="text-lg font-bold mb-4">Group Information</h3>
            <div className="grid grid-cols-3 gap-6">
              <div>
                <div className="text-sm text-gray-600 mb-1">Class</div>
                <div className="font-bold">{group.class}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Project</div>
                <div className="font-bold">{group.projectName}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Deadline</div>
                <div className="font-bold">
                  {new Date(group.deadline).toLocaleDateString('en-US', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
        })}
                </div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-xl font-bold mb-4">Students ({mockStudents.length})</h3>
            <div className="space-y-4">
              {mockStudents.map((student) => (<div key={student.id} className="border-2 border-gray-400 p-6 hover:border-black cursor-pointer" onClick={() => router.push(`/projects/${projectId}/groups/${groupId}/students/${student.id}`)}>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-6 flex-1">
                      <div className="w-16 h-16 border-2 border-gray-400 flex items-center justify-center">
                        <span className="text-sm font-bold">
                          {student.name.split(' ').map((n) => n[0]).join('')}
                        </span>
                      </div>
                      <div className="flex-1">
                        <div className="font-bold mb-1">{student.name}</div>
                        <div className="text-sm text-gray-600 space-x-4">
                          <span>{student.studentNumber}</span>
                          <span>| {student.email}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      {student.overallScore && (<div className="text-center">
                          <div className="text-sm text-gray-600 mb-1">Grade</div>
                          <div className="text-3xl font-bold">{student.overallScore}</div>
                        </div>)}
                      <div className="border border-gray-400 px-3 py-1 text-sm">
                        [
                        {student.assessmentStatus === 'completed'
                ? 'COMPLETED'
                : student.assessmentStatus === 'in-progress'
                    ? 'IN PROGRESS'
                    : 'NOT STARTED'}
                        ]
                      </div>
                      <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-200">
                        [ASSESS]
                      </button>
                    </div>
                  </div>
                </div>))}
            </div>
          </div>
        </div>

        <div className="col-span-1">
          <div className="border-2 border-gray-400 p-6 sticky top-8">
            <h3 className="font-bold mb-4">Evidence Files</h3>

            <div className="mb-6">
              <div className="text-sm font-bold mb-2">Uploaded ({evidenceFiles.length})</div>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {evidenceFiles.map((file) => (<div key={file.id} className="border border-gray-400 p-2 text-xs">
                    <div className="font-bold mb-1">{file.name}</div>
                    <div className="text-gray-600">
                      {file.type} • {file.uploadedBy}
                    </div>
                  </div>))}
              </div>
            </div>

            <div className="border-t-2 border-gray-300 pt-4">
              <div className="text-sm font-bold mb-2">Add Evidence</div>
              <div className={`border-2 border-dashed ${dragActive ? 'border-gray-900 bg-gray-100' : 'border-gray-400'} p-6 text-center transition-all`} onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}>
                <div className="text-3xl mb-2">📁</div>
                <div className="text-xs mb-2">Drop files here</div>
                <input type="file" multiple onChange={handleFileInput} className="hidden" id="evidence-upload"/>
                <label htmlFor="evidence-upload" className="inline-block border border-gray-400 px-3 py-1 text-xs cursor-pointer hover:bg-gray-100">
                  [BROWSE]
                </label>
              </div>

              {uploadedFiles.length > 0 && (<div className="mt-3 space-y-1">
                  {uploadedFiles.map((file, index) => (<div key={index} className="flex justify-between items-center border border-gray-400 p-2 text-xs">
                      <span className="truncate">{file.name}</span>
                      <button onClick={() => setUploadedFiles(uploadedFiles.filter((_, i) => i !== index))} className="border border-gray-400 px-2 py-0.5 hover:bg-gray-100">
                        [X]
                      </button>
                    </div>))}
                </div>)}
            </div>
          </div>
        </div>
      </div>
    </div>);
}
