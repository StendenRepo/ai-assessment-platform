'use client';
import { useState } from 'react';
export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const tabs = [
    { key: 'general', label: 'General' },
    { key: 'ai', label: 'AI Configuration' },
    { key: 'privacy', label: 'Privacy & GDPR' },
    { key: 'integration', label: 'Integrations' },
  ];
  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Settings</h2>
        <p className="text-gray-600">
          Configure system preferences and settings
        </p>
      </div>

      <div className="grid grid-cols-4 gap-8">
        <div className="col-span-1">
          <div className="border-2 border-gray-400 sticky top-8">
            {tabs.map((tab, i) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`w-full text-left px-4 py-3 ${i < tabs.length - 1 ? 'border-b-2 border-gray-400' : ''} ${activeTab === tab.key ? 'bg-gray-900 text-white font-bold' : 'hover:bg-gray-100'}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="col-span-3 space-y-6">
          {activeTab === 'general' && (
            <>
              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">Profile Settings</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block font-bold mb-2">First Name</label>
                      <input
                        type="text"
                        defaultValue="John"
                        className="w-full border-2 border-gray-400 px-4 py-2"
                      />
                    </div>
                    <div>
                      <label className="block font-bold mb-2">Last Name</label>
                      <input
                        type="text"
                        defaultValue="Smith"
                        className="w-full border-2 border-gray-400 px-4 py-2"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block font-bold mb-2">Email</label>
                    <input
                      type="email"
                      defaultValue="j.smith@university.edu"
                      className="w-full border-2 border-gray-400 px-4 py-2"
                    />
                  </div>
                  <div>
                    <label className="block font-bold mb-2">Department</label>
                    <input
                      type="text"
                      defaultValue="Computer Science"
                      className="w-full border-2 border-gray-400 px-4 py-2"
                    />
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">System Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block font-bold mb-2">Language</label>
                    <select className="w-full border-2 border-gray-400 px-4 py-2">
                      <option value="en">English</option>
                      <option value="nl">Nederlands</option>
                      <option value="de">Deutsch</option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-bold mb-2">Timezone</label>
                    <select className="w-full border-2 border-gray-400 px-4 py-2">
                      <option value="europe/amsterdam">
                        Europe/Amsterdam (UTC+1)
                      </option>
                      <option value="europe/london">
                        Europe/London (UTC+0)
                      </option>
                      <option value="america/new_york">
                        America/New York (UTC-5)
                      </option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-bold mb-2">Date Format</label>
                    <select className="w-full border-2 border-gray-400 px-4 py-2">
                      <option value="dd-mm-yyyy">DD-MM-YYYY</option>
                      <option value="mm-dd-yyyy">MM-DD-YYYY</option>
                      <option value="yyyy-mm-dd">YYYY-MM-DD</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">Notifications</h3>
                <div className="space-y-3">
                  {[
                    { label: 'Email for new projects', defaultChecked: true },
                    {
                      label: 'Email for completed AI analyses',
                      defaultChecked: true,
                    },
                    {
                      label: 'Email for approaching deadlines',
                      defaultChecked: true,
                    },
                    { label: 'Weekly summary reports', defaultChecked: false },
                  ].map((item) => (
                    <label
                      key={item.label}
                      className="flex items-center justify-between"
                    >
                      <span>{item.label}</span>
                      <input
                        type="checkbox"
                        className="w-5 h-5"
                        defaultChecked={item.defaultChecked}
                      />
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}

          {activeTab === 'ai' && (
            <>
              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">
                  AI Model Configuration
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block font-bold mb-2">
                      Overlap Detection Sensitivity
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      defaultValue="70"
                      className="w-full"
                    />
                    <div className="flex justify-between text-sm text-gray-600">
                      <span>Less Sensitive</span>
                      <span>More Sensitive</span>
                    </div>
                  </div>
                  <div>
                    <label className="block font-bold mb-2">
                      Minimum Confidence (%)
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      defaultValue="75"
                      className="w-full border-2 border-gray-400 px-4 py-2"
                    />
                    <p className="text-sm text-gray-600 mt-1">
                      AI suggestions below this threshold will not be displayed
                    </p>
                  </div>
                  <div>
                    <label className="block font-bold mb-2">
                      Automatic Evidence Linking
                    </label>
                    <select className="w-full border-2 border-gray-400 px-4 py-2">
                      <option value="aggressive">
                        Aggressive - Link all possible matches
                      </option>
                      <option value="balanced">
                        Balanced - Only high confidence
                      </option>
                      <option value="conservative">
                        Conservative - Only very likely matches
                      </option>
                      <option value="manual">
                        Manual - No automatic linking
                      </option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">Source Code Analysis</h3>
                <div className="space-y-3">
                  {[
                    'Analyze Git commit history',
                    'Detect code duplication',
                    'Analyze code comments and documentation',
                    'Track file changes over time',
                  ].map((item) => (
                    <label
                      key={item}
                      className="flex items-center justify-between"
                    >
                      <span>{item}</span>
                      <input
                        type="checkbox"
                        className="w-5 h-5"
                        defaultChecked
                      />
                    </label>
                  ))}
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6 bg-yellow-50">
                <div className="font-bold mb-2">[!] Important</div>
                <p className="text-sm text-gray-600">
                  Changes to AI configuration will be applied to new analyses.
                  Existing projects will not be automatically re-analyzed.
                </p>
              </div>
            </>
          )}

          {activeTab === 'privacy' && (
            <>
              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">Data Storage</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block font-bold mb-2">
                      Data Retention Period
                    </label>
                    <select className="w-full border-2 border-gray-400 px-4 py-2">
                      <option value="30">
                        30 days after project completion
                      </option>
                      <option value="90">
                        90 days after project completion
                      </option>
                      <option value="180">
                        180 days after project completion
                      </option>
                      <option value="365">
                        1 year after project completion
                      </option>
                      <option value="infinite">
                        Unlimited (manual deletion)
                      </option>
                    </select>
                  </div>
                  <div>
                    <label className="block font-bold mb-2">
                      Automatic Anonymization
                    </label>
                    <select className="w-full border-2 border-gray-400 px-4 py-2">
                      <option value="never">Never</option>
                      <option value="30">After 30 days</option>
                      <option value="90">After 90 days</option>
                      <option value="180">After 180 days</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">GDPR Compliance</h3>
                <div className="space-y-3">
                  <label className="flex items-center justify-between">
                    <span>Log all data access</span>
                    <input
                      type="checkbox"
                      className="w-5 h-5"
                      defaultChecked
                      disabled
                    />
                  </label>
                  <label className="flex items-center justify-between">
                    <span>Require student consent for analysis</span>
                    <input type="checkbox" className="w-5 h-5" defaultChecked />
                  </label>
                  <label className="flex items-center justify-between">
                    <span>Anonymize data in exports</span>
                    <input type="checkbox" className="w-5 h-5" />
                  </label>
                  <label className="flex items-center justify-between">
                    <span>Store audit trail for 7 years</span>
                    <input
                      type="checkbox"
                      className="w-5 h-5"
                      defaultChecked
                      disabled
                    />
                  </label>
                </div>
                <div className="mt-4 pt-4 border-t-2 border-gray-300">
                  <p className="text-sm text-gray-600 mb-3">
                    Some settings are required by GDPR legislation and cannot be
                    disabled.
                  </p>
                  <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100">
                    [DOWNLOAD GDPR COMPLIANCE REPORT]
                  </button>
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">Data Deletion</h3>
                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-3">
                      Students have the right to have their personal data
                      deleted.
                    </p>
                    <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100">
                      [PROCESS DELETION REQUEST]
                    </button>
                  </div>
                  <div className="border-t-2 border-gray-300 pt-4">
                    <p className="text-sm text-gray-600 mb-3">
                      Delete all data older than the configured retention
                      period.
                    </p>
                    <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100">
                      [RUN AUTOMATIC CLEANUP]
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeTab === 'integration' && (
            <>
              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">External Systems</h3>
                <div className="space-y-4">
                  <div className="border-2 border-gray-400 p-4">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="font-bold mb-1">
                          [GITHUB] GitHub Integration
                        </div>
                        <div className="text-sm text-gray-600">
                          Automatically analyze Git repositories
                        </div>
                      </div>
                      <span className="border border-green-600 text-green-600 px-2 py-1 text-xs">
                        [ACTIVE]
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="text-sm">
                        <span className="font-bold">API Key:</span>{' '}
                        ghp_**********************
                      </div>
                      <div className="flex gap-2">
                        <button className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100">
                          [CONFIGURE]
                        </button>
                        <button className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100">
                          [TEST CONNECTION]
                        </button>
                        <button className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100">
                          [DEACTIVATE]
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="border-2 border-gray-400 p-4">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="font-bold mb-1">
                          [LMS] Learning Management System
                        </div>
                        <div className="text-sm text-gray-600">
                          Import courses and students from LMS
                        </div>
                      </div>
                      <span className="border border-gray-400 text-gray-600 px-2 py-1 text-xs">
                        [NOT ACTIVE]
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="text-sm text-gray-600">
                        Connect to Canvas, Blackboard, Moodle or other LMS
                        systems
                      </div>
                      <button className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100">
                        [CONFIGURE INTEGRATION]
                      </button>
                    </div>
                  </div>

                  <div className="border-2 border-gray-400 p-4">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <div className="font-bold mb-1">
                          [EMAIL] Email Server
                        </div>
                        <div className="text-sm text-gray-600">
                          SMTP configuration for notifications
                        </div>
                      </div>
                      <span className="border border-green-600 text-green-600 px-2 py-1 text-xs">
                        [ACTIVE]
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="text-sm">
                        <span className="font-bold">Server:</span>{' '}
                        smtp.university.edu:587
                      </div>
                      <div className="flex gap-2">
                        <button className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100">
                          [CONFIGURE]
                        </button>
                        <button className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100">
                          [TEST EMAIL]
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-400 p-6">
                <h3 className="text-lg font-bold mb-4">API Access</h3>
                <div className="space-y-4">
                  <p className="text-sm text-gray-600">
                    Generate API keys for external access to the system. Use for
                    custom integrations.
                  </p>
                  <div className="border-2 border-gray-400 p-3">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-bold text-sm">
                        Production API Key
                      </span>
                      <span className="text-xs border border-gray-400 px-2 py-1">
                        [ACTIVE]
                      </span>
                    </div>
                    <div className="text-xs font-mono bg-gray-100 p-2 border border-gray-400">
                      api_prod_************************************************
                    </div>
                  </div>
                  <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100">
                    [+ GENERATE NEW API KEY]
                  </button>
                </div>
              </div>
            </>
          )}

          <div className="flex justify-end gap-4">
            <button className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100">
              [CANCEL]
            </button>
            <button className="border-2 border-gray-400 bg-gray-900 text-white px-6 py-3 hover:bg-gray-700">
              [SAVE]
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
