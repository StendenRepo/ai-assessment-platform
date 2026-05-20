'use client';

import { useState, useEffect, useRef } from 'react';
import { mockStudents, mockContributions, mockCriteria } from '@/lib/mockData';
import AIInsightsPanel from './AIInsightsPanel';

export default function StudentAssessment({ studentId, projectId, groupId }) {
  const student = mockStudents.find((s) => s.id === studentId);
  const [currentTab, setCurrentTab] = useState(0);
  const [expandedContribution, setExpandedContribution] = useState(null);
  const [scores, setScores] = useState({});
  const [comments, setComments] = useState({});
  const [showConsentPopup, setShowConsentPopup] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (isRecording && !isPaused) {
      timerRef.current = setInterval(
        () => setRecordingTime((t) => t + 1),
        1000
      );
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isRecording, isPaused]);

  if (!student) return <div>Student not found</div>;

  const handleScoreChange = (criterionId, value) => {
    const numValue = parseFloat(value);
    if (!isNaN(numValue)) setScores({ ...scores, [criterionId]: numValue });
  };

  const calculateOverallScore = () => {
    const vals = Object.values(scores);
    if (vals.length === 0) return 0;
    return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
  };

  const handleConsentSubmit = () => {
    if (consentGiven) {
      setShowConsentPopup(false);
      setIsRecording(true);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  return (
    <div>
      <div className="border-2 border-gray-400 p-6 mb-8">
        <div className="flex items-center gap-6">
          <div className="w-20 h-20 border-2 border-gray-400 flex items-center justify-center">
            <span className="font-bold">
              {student.name
                .split(' ')
                .map((n) => n[0])
                .join('')}
            </span>
          </div>
          <div className="flex-1">
            <h2 className="text-2xl font-bold mb-1">{student.name}</h2>
            <div className="text-gray-600">
              {student.studentNumber} • {student.email}
            </div>
          </div>
          <div className="text-center border-l-2 border-gray-400 pl-8">
            <div className="text-sm text-gray-600 mb-1">Current Score</div>
            <div className="text-4xl font-bold">{calculateOverallScore()}</div>
          </div>
          {!isRecording && (
            <button
              onClick={() => setShowConsentPopup(true)}
              className="border-2 border-gray-400 bg-gray-900 text-white px-6 py-3 hover:bg-gray-700"
            >
              [START ASSESSMENT]
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-8">
        <div className={isRecording ? 'col-span-2' : 'col-span-3'}>
          <div className="border-2 border-gray-400">
            <div className="border-b-2 border-gray-400 flex">
              <button
                className={`px-6 py-3 border-r-2 border-gray-400 ${currentTab === 0 ? 'bg-gray-300 font-bold' : ''}`}
                onClick={() => setCurrentTab(0)}
              >
                Contributions &amp; Evidence
              </button>
              <button
                className={`px-6 py-3 ${currentTab === 1 ? 'bg-gray-300 font-bold' : ''}`}
                onClick={() => setCurrentTab(1)}
              >
                Assessment
              </button>
            </div>

            <div className="p-6">
              {currentTab === 0 && (
                <div>
                  <div className="mb-6">
                    <h3 className="text-lg font-bold mb-2">
                      Detected Contributions
                    </h3>
                    <p className="text-sm text-gray-600">
                      Automatically detected contributions with supporting
                      evidence
                    </p>
                  </div>

                  <div className="space-y-4">
                    {mockContributions.map((contribution) => (
                      <div
                        key={contribution.id}
                        className="border-2 border-gray-400"
                      >
                        <button
                          className="w-full p-4 text-left hover:bg-gray-100 flex justify-between items-center"
                          onClick={() =>
                            setExpandedContribution(
                              expandedContribution === contribution.id
                                ? null
                                : contribution.id
                            )
                          }
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-12 h-12 border-2 border-gray-400 flex items-center justify-center text-xs">
                              [
                              {contribution.type === 'code'
                                ? 'CODE'
                                : contribution.type === 'documentation'
                                  ? 'DOC'
                                  : contribution.type === 'presentation'
                                    ? 'PRES'
                                    : 'RES'}
                              ]
                            </div>
                            <div>
                              <div className="font-bold mb-1">
                                {contribution.title}
                              </div>
                              <div className="text-sm text-gray-600">
                                {contribution.evidenceFiles.length} evidence
                                files
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            {contribution.aiConfidence && (
                              <span className="text-sm border border-gray-400 px-2 py-1">
                                AI:{' '}
                                {(contribution.aiConfidence * 100).toFixed(0)}%
                              </span>
                            )}
                            <span className="text-xl">
                              {expandedContribution === contribution.id
                                ? '▼'
                                : '▶'}
                            </span>
                          </div>
                        </button>

                        {expandedContribution === contribution.id && (
                          <div className="border-t-2 border-gray-400 p-4 bg-gray-50">
                            <p className="text-sm text-gray-600 mb-4">
                              {contribution.description}
                            </p>

                            <div className="mb-4">
                              <div className="font-bold mb-2">
                                Evidence ({contribution.evidenceFiles.length})
                              </div>
                              <div className="space-y-2">
                                {contribution.evidenceFiles.map((evidence) => (
                                  <div
                                    key={evidence.id}
                                    className="border border-gray-400 p-3"
                                  >
                                    <div className="flex justify-between items-start mb-2">
                                      <div className="font-bold text-sm">
                                        {evidence.fileName}
                                      </div>
                                      <button className="text-xs border border-gray-400 px-2 py-1">
                                        [VIEW SOURCE →]
                                      </button>
                                    </div>
                                    {evidence.excerpt && (
                                      <div className="bg-white border border-gray-400 p-2 text-xs font-mono mb-2">
                                        {evidence.excerpt}
                                      </div>
                                    )}
                                    <div className="text-xs text-gray-600">
                                      Uploaded:{' '}
                                      {new Date(
                                        evidence.uploadDate
                                      ).toLocaleDateString('en-US')}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>

                            {contribution.linkedCriteria.length > 0 && (
                              <div>
                                <div className="font-bold mb-2">
                                  Linked Criteria
                                </div>
                                <div className="flex gap-2">
                                  {contribution.linkedCriteria.map(
                                    (criterionId) => {
                                      const criterion = mockCriteria.find(
                                        (c) => c.id === criterionId
                                      );
                                      return criterion ? (
                                        <span
                                          key={criterionId}
                                          className="text-xs border border-gray-400 px-2 py-1"
                                        >
                                          {criterion.name}
                                        </span>
                                      ) : null;
                                    }
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {currentTab === 1 && (
                <div>
                  <div className="mb-6">
                    <h3 className="text-lg font-bold mb-2">
                      Assessment Criteria
                    </h3>
                    <p className="text-sm text-gray-600">
                      Provide a score and explanation for each criterion
                    </p>
                  </div>

                  <div className="space-y-4">
                    {mockCriteria.map((criterion) => (
                      <div
                        key={criterion.id}
                        className="border-2 border-gray-400 p-4"
                      >
                        <div className="flex justify-between items-start mb-4">
                          <div>
                            <h4 className="font-bold mb-1">{criterion.name}</h4>
                            <p className="text-sm text-gray-600">
                              {criterion.description}
                            </p>
                          </div>
                          <span className="text-xs border border-gray-400 px-2 py-1">
                            [{criterion.category}]
                          </span>
                        </div>

                        <div className="grid grid-cols-4 gap-4">
                          <div>
                            <label className="block text-sm mb-1">Score</label>
                            <input
                              type="number"
                              min="0"
                              max={criterion.maxScore}
                              step="0.5"
                              value={scores[criterion.id] || ''}
                              onChange={(e) =>
                                handleScoreChange(criterion.id, e.target.value)
                              }
                              className="w-full border-2 border-gray-400 px-3 py-2"
                              placeholder="0"
                            />
                            <div className="text-xs text-gray-600 mt-1">
                              Max: {criterion.maxScore}
                            </div>
                          </div>
                          <div className="col-span-3">
                            <label className="block text-sm mb-1">
                              Explanation
                            </label>
                            <textarea
                              rows={3}
                              value={comments[criterion.id] || ''}
                              onChange={(e) =>
                                setComments({
                                  ...comments,
                                  [criterion.id]: e.target.value,
                                })
                              }
                              className="w-full border-2 border-gray-400 px-3 py-2"
                              placeholder="Provide an explanation..."
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="flex gap-4 justify-end mt-6">
                    <button className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100">
                      [SAVE AS DRAFT]
                    </button>
                    <button className="border-2 border-gray-400 bg-gray-900 text-white px-6 py-3 hover:bg-gray-700">
                      [COMPLETE ASSESSMENT]
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {isRecording && (
          <div className="col-span-1 space-y-4">
            <div className="border-2 border-gray-400 p-6 sticky top-8">
              <h3 className="font-bold mb-4">Recording Controls</h3>

              <div className="border-2 border-gray-400 p-4 mb-4 bg-red-50">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-3 h-3 rounded-full bg-red-600 animate-pulse"></div>
                  <span className="font-bold">RECORDING</span>
                </div>
                <div className="text-2xl font-bold font-mono">
                  {formatTime(recordingTime)}
                </div>
              </div>

              <div className="space-y-3">
                <button
                  onClick={() => setIsPaused(!isPaused)}
                  className="w-full border-2 border-gray-400 px-4 py-3 hover:bg-gray-100"
                >
                  {isPaused ? '[RESUME]' : '[PAUSE]'}
                </button>
                <button
                  onClick={() => {
                    setIsRecording(false);
                    setRecordingTime(0);
                    setIsPaused(false);
                  }}
                  className="w-full border-2 border-gray-400 bg-gray-900 text-white px-4 py-3 hover:bg-gray-700"
                >
                  [STOP &amp; SAVE]
                </button>
              </div>

              <div className="mt-6 text-xs text-gray-600 border-t-2 border-gray-300 pt-4">
                <div className="font-bold mb-2">[i] Recording Info</div>
                <p>
                  Audio and video are being recorded for assessment purposes.
                  The recording will be stored securely and only accessible to
                  authorized personnel.
                </p>
              </div>
            </div>

            <AIInsightsPanel studentId={studentId} />
          </div>
        )}
      </div>

      {showConsentPopup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white border-4 border-gray-400 p-8 max-w-lg">
            <h3 className="text-xl font-bold mb-4">
              Recording Consent Required
            </h3>

            <div className="mb-6 text-sm space-y-3">
              <p>
                Before starting the assessment, we need your consent to record
                this session.
              </p>
              <p>
                The recording will include audio and video, and will be used
                solely for assessment purposes. It will be stored securely
                according to GDPR guidelines.
              </p>
            </div>

            <div className="border-2 border-gray-400 p-4 mb-6">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consentGiven}
                  onChange={(e) => setConsentGiven(e.target.checked)}
                  className="w-5 h-5 mt-0.5"
                />
                <span className="text-sm">
                  I consent to this assessment session being recorded. I
                  understand that the recording will be used for assessment
                  purposes only and will be handled in accordance with GDPR
                  regulations.
                </span>
              </label>
            </div>

            <div className="flex gap-4 justify-end">
              <button
                onClick={() => {
                  setShowConsentPopup(false);
                  setConsentGiven(false);
                }}
                className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100"
              >
                [CANCEL]
              </button>
              <button
                onClick={handleConsentSubmit}
                disabled={!consentGiven}
                className={`border-2 border-gray-400 px-6 py-3 ${
                  consentGiven
                    ? 'bg-gray-900 text-white hover:bg-gray-700'
                    : 'opacity-50 cursor-not-allowed'
                }`}
              >
                [START RECORDING →]
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
