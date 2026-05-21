'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function ProjectSetup() {
  const router = useRouter();
  const [projectName, setProjectName] = useState('');
  const [course, setCourse] = useState('');
  const [className, setClassName] = useState('');
  const [deadline, setDeadline] = useState('');
  const [description, setDescription] = useState('');
  const [students, setStudents] = useState([{ email: '', studentNumber: '' }]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);

  const addStudentField = () =>
    setStudents([...students, { email: '', studentNumber: '' }]);

  const updateStudent = (index, field, value) => {
    const updated = [...students];
    updated[index][field] = value;
    setStudents(updated);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
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

  const handleCreateProject = () => {
    const projectId = `proj-${Date.now()}`;
    router.push(`/projects/${projectId}/criteria`);
  };

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Create New Project</h2>
        <p className="text-gray-600">
          Configure a new group project for assessment
        </p>
      </div>

      <div className="max-w-4xl space-y-6">
        <div className="border-2 border-gray-400 p-6">
          <h3 className="text-lg font-bold mb-4">Project Information</h3>
          <div className="space-y-4">
            <div>
              <label className="block font-bold mb-2">Project Name *</label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="w-full border-2 border-gray-400 px-4 py-2"
                placeholder="e.g. E-Commerce Platform"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block font-bold mb-2">Course *</label>
                <input
                  type="text"
                  value={course}
                  onChange={(e) => setCourse(e.target.value)}
                  className="w-full border-2 border-gray-400 px-4 py-2"
                  placeholder="e.g. Advanced Web Development"
                />
              </div>
              <div>
                <label className="block font-bold mb-2">Class *</label>
                <input
                  type="text"
                  value={className}
                  onChange={(e) => setClassName(e.target.value)}
                  className="w-full border-2 border-gray-400 px-4 py-2"
                  placeholder="e.g. CS401-A"
                />
              </div>
            </div>

            <div>
              <label className="block font-bold mb-2">Deadline *</label>
              <input
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="w-full border-2 border-gray-400 px-4 py-2"
              />
            </div>

            <div>
              <label className="block font-bold mb-2">
                Project Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                className="w-full border-2 border-gray-400 px-4 py-2"
                placeholder="Brief description of the project..."
              />
            </div>
          </div>
        </div>

        <div className="border-2 border-gray-400 p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold">Students</h3>
            <button
              onClick={addStudentField}
              className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100"
            >
              [+ ADD STUDENT]
            </button>
          </div>

          <div className="space-y-3">
            {students.map((student, index) => (
              <div key={index} className="flex gap-2">
                <input
                  type="text"
                  value={student.studentNumber}
                  onChange={(e) =>
                    updateStudent(index, 'studentNumber', e.target.value)
                  }
                  className="w-48 border-2 border-gray-400 px-4 py-2"
                  placeholder="Student Number"
                />
                <input
                  type="email"
                  value={student.email}
                  onChange={(e) =>
                    updateStudent(index, 'email', e.target.value)
                  }
                  className="flex-1 border-2 border-gray-400 px-4 py-2"
                  placeholder="student@university.edu"
                />
                {students.length > 1 && (
                  <button
                    onClick={() =>
                      setStudents(students.filter((_, i) => i !== index))
                    }
                    className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100"
                  >
                    [X]
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="border-2 border-gray-400 p-6">
          <h3 className="text-lg font-bold mb-4">Evidence Sources Upload</h3>

          <div className="space-y-4">
            <div
              className={`border-4 border-dashed ${
                dragActive ? 'border-gray-900 bg-gray-100' : 'border-gray-400'
              } p-12 text-center transition-all`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <div className="text-6xl mb-4">📁</div>
              <div className="text-lg font-bold mb-2">Drop Files Here</div>
              <div className="text-sm text-gray-600 mb-4">
                or click to browse
              </div>

              <input
                type="file"
                multiple
                onChange={handleFileInput}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="inline-block border-2 border-gray-400 px-6 py-3 cursor-pointer hover:bg-gray-100"
              >
                [BROWSE FILES]
              </label>

              <div className="text-xs text-gray-600 mt-4">
                Supported: Code files, documents, PDFs, images (Max 100MB per
                file)
              </div>
            </div>

            {uploadedFiles.length > 0 && (
              <div>
                <div className="font-bold mb-2">
                  Uploaded Files ({uploadedFiles.length})
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {uploadedFiles.map((file, index) => (
                    <div
                      key={index}
                      className="flex justify-between items-center border border-gray-400 p-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="text-2xl">📄</div>
                        <div>
                          <div className="font-bold text-sm">{file.name}</div>
                          <div className="text-xs text-gray-600">
                            {(file.size / 1024).toFixed(2)} KB
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() =>
                          setUploadedFiles(
                            uploadedFiles.filter((_, i) => i !== index)
                          )
                        }
                        className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100"
                      >
                        [REMOVE]
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-4 justify-end">
          <button
            onClick={() => router.push('/projects')}
            className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100"
          >
            [CANCEL]
          </button>
          <button className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100">
            [SAVE AS DRAFT]
          </button>
          <button
            onClick={handleCreateProject}
            className="border-2 border-gray-400 bg-gray-900 text-white px-6 py-3 hover:bg-gray-700"
          >
            [CREATE PROJECT →]
          </button>
        </div>
      </div>
    </div>
  );
}
