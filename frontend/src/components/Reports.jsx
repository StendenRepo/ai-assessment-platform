'use client';
import { useState } from 'react';
import { mockProjects } from '@/lib/mockData';
export default function Reports() {
    const [selectedProject, setSelectedProject] = useState('');
    const [reportType, setReportType] = useState('individual');
    const [exportFormat, setExportFormat] = useState('pdf');
    return (<div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Reports & Export</h2>
        <p className="text-gray-600">Generate and export assessment reports</p>
      </div>

      <div className="grid grid-cols-3 gap-8">
        <div className="col-span-2 space-y-6">
          <div className="border-2 border-gray-400 p-6">
            <h3 className="text-lg font-bold mb-4">Report Configuration</h3>

            <div className="space-y-4">
              <div>
                <label className="block font-bold mb-2">Select Project *</label>
                <select value={selectedProject} onChange={(e) => setSelectedProject(e.target.value)} className="w-full border-2 border-gray-400 px-4 py-2">
                  <option value="">-- Choose a project --</option>
                  {mockProjects.map((project) => (<option key={project.id} value={project.id}>
                      {project.name} - {project.course}
                    </option>))}
                </select>
              </div>

              <div>
                <label className="block font-bold mb-2">Report Type *</label>
                <div className="space-y-2">
                  {[
            {
                value: 'individual',
                label: 'Individual Student Reports',
                desc: 'Generate separate report per student with scores and feedback',
            },
            {
                value: 'group',
                label: 'Group Overview Report',
                desc: 'Overview of all students in the project with comparison',
            },
            {
                value: 'ai-insights',
                label: 'AI Analysis Report',
                desc: 'Overview of AI insights, overlap detection and warnings',
            },
            {
                value: 'evidence',
                label: 'Evidence Audit Report',
                desc: 'Detailed overview of all evidence and traceability',
            },
        ].map((type) => (<label key={type.value} className="flex items-center gap-3 border-2 border-gray-400 p-3 hover:bg-gray-50 cursor-pointer">
                      <input type="radio" name="reportType" value={type.value} checked={reportType === type.value} onChange={(e) => setReportType(e.target.value)} className="w-4 h-4"/>
                      <div>
                        <div className="font-bold">{type.label}</div>
                        <div className="text-sm text-gray-600">{type.desc}</div>
                      </div>
                    </label>))}
                </div>
              </div>

              <div>
                <label className="block font-bold mb-2">Export Format *</label>
                <div className="grid grid-cols-4 gap-2">
                  {['pdf', 'excel', 'csv', 'json'].map((fmt) => (<button key={fmt} onClick={() => setExportFormat(fmt)} className={`border-2 border-gray-400 px-4 py-2 ${exportFormat === fmt ? 'bg-gray-900 text-white' : 'hover:bg-gray-100'}`}>
                      [{fmt.toUpperCase()}]
                    </button>))}
                </div>
              </div>

              <div className="border-t-2 border-gray-300 pt-4">
                <label className="block font-bold mb-2">Options</label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" className="w-4 h-4" defaultChecked/>
                    <span className="text-sm">Include assessment criteria</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" className="w-4 h-4" defaultChecked/>
                    <span className="text-sm">Include AI analyses and suggestions</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" className="w-4 h-4"/>
                    <span className="text-sm">Include evidence links and source files</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" className="w-4 h-4"/>
                    <span className="text-sm">Anonymize student data</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="flex gap-4 justify-end mt-6">
              <button className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100">
                [PREVIEW]
              </button>
              <button className="border-2 border-gray-400 bg-gray-900 text-white px-6 py-3 hover:bg-gray-700">
                [GENERATE REPORT →]
              </button>
            </div>
          </div>

          <div className="border-2 border-gray-400 p-6">
            <h3 className="text-lg font-bold mb-4">Recent Reports</h3>
            <div className="space-y-3">
              {[
            { name: 'E-Commerce Platform - Individual Reports', date: '05-15-2026 2:32 PM', format: 'PDF', files: 4 },
            { name: 'Machine Learning Model - AI Analysis', date: '05-14-2026 10:15 AM', format: 'Excel', files: 1 },
            { name: 'Mobile App Prototype - Group Overview', date: '05-12-2026 4:45 PM', format: 'PDF', files: 1 },
        ].map((report, i) => (<div key={i} className="border-2 border-gray-400 p-4 flex justify-between items-center">
                  <div>
                    <div className="font-bold mb-1">{report.name}</div>
                    <div className="text-sm text-gray-600">
                      Generated: {report.date} • {report.format} • {report.files} file{report.files > 1 ? 's' : ''}
                    </div>
                  </div>
                  <button className="border-2 border-gray-400 px-4 py-2 text-sm hover:bg-gray-100">
                    [DOWNLOAD →]
                  </button>
                </div>))}
            </div>
          </div>
        </div>

        <div className="col-span-1">
          <div className="border-2 border-gray-400 p-6 mb-4 sticky top-8">
            <h3 className="font-bold mb-4">[i] Report Types</h3>
            <div className="space-y-4 text-sm">
              {[
            { title: 'Individual', desc: 'Personal report per student with scores, feedback and evidence overview.' },
            { title: 'Group Overview', desc: 'Comparison of all students with averages and distribution of scores.' },
            { title: 'AI Analysis', desc: 'Detailed overview of AI insights, overlap detections and warnings.' },
            { title: 'Evidence Audit', desc: 'Complete overview of all evidence documents with traceability to sources.' },
        ].map((item, i) => (<div key={i} className={i > 0 ? 'border-t-2 border-gray-300 pt-4' : ''}>
                  <div className="font-bold mb-1">{item.title}</div>
                  <p className="text-gray-600">{item.desc}</p>
                </div>))}
            </div>
          </div>

          <div className="border-2 border-gray-400 p-4">
            <div className="font-bold mb-2 text-sm">[!] Privacy</div>
            <p className="text-xs text-gray-600">
              Reports may contain sensitive student data. Handle these according to GDPR guidelines
              and share only with authorized persons.
            </p>
          </div>
        </div>
      </div>
    </div>);
}
