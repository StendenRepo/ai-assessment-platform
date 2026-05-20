'use client';

import { useState } from 'react';
import { mockAIInsights } from '@/lib/mockData';

export default function AIInsightsPanel({ studentId }) {
  const relevantInsights = mockAIInsights.filter((insight) =>
    insight.affectedStudents.includes(studentId)
  );
  const [expandedInsight, setExpandedInsight] = useState(null);

  return (
    <div className="space-y-4">
      <div className="border-2 border-gray-400 p-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 border-2 border-gray-400 flex items-center justify-center text-xs">
            [AI]
          </div>
          <div>
            <div className="font-bold">AI Assistant</div>
            <div className="text-xs text-gray-600">
              {relevantInsights.length} insights for this student
            </div>
          </div>
        </div>
      </div>

      <div className="border-2 border-gray-400 p-4">
        <div className="font-bold mb-2 text-sm">[i] Privacy Guarantee</div>
        <p className="text-xs text-gray-600">
          All AI analyses are performed on-premises and comply with GDPR. All
          suggestions are traceable to source files.
        </p>
      </div>

      <div className="border-2 border-gray-400">
        <div className="border-b-2 border-gray-400 p-4">
          <h3 className="font-bold mb-1">AI Insights</h3>
          <p className="text-xs text-gray-600">
            Detected patterns and warnings
          </p>
        </div>

        <div className="p-4">
          {relevantInsights.length === 0 ? (
            <div className="border-2 border-gray-400 p-6 text-center">
              <div className="text-4xl mb-2">✓</div>
              <div className="text-sm text-gray-600">
                No notable insights found
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {relevantInsights.map((insight) => (
                <div key={insight.id} className="border-2 border-gray-400">
                  <button
                    className="w-full p-3 text-left hover:bg-gray-100 flex justify-between items-center"
                    onClick={() =>
                      setExpandedInsight(
                        expandedInsight === insight.id ? null : insight.id
                      )
                    }
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <div className="text-xl">
                        {insight.type === 'overlap'
                          ? '⚠'
                          : insight.type === 'suggestion'
                            ? 'i'
                            : '!'}
                      </div>
                      <div className="flex-1">
                        <div className="font-bold text-sm">{insight.title}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs border border-gray-400 px-2 py-1">
                        [{insight.severity.toUpperCase()}]
                      </span>
                      <span className="text-sm">
                        {expandedInsight === insight.id ? '▼' : '▶'}
                      </span>
                    </div>
                  </button>

                  {expandedInsight === insight.id && (
                    <div className="border-t-2 border-gray-400 p-3 bg-gray-50">
                      <div className="mb-3">
                        <span className="text-xs border border-gray-400 px-2 py-1 inline-block mb-2">
                          [
                          {insight.type === 'overlap'
                            ? 'OVERLAP'
                            : insight.type === 'suggestion'
                              ? 'SUGGESTION'
                              : 'ANOMALY'}
                          ]
                        </span>
                        <p className="text-sm text-gray-600">
                          {insight.description}
                        </p>
                      </div>

                      {insight.sourceFiles.length > 0 && (
                        <div className="mb-3">
                          <div className="text-xs font-bold mb-2">
                            Source Files ({insight.sourceFiles.length})
                          </div>
                          <div className="space-y-1">
                            {insight.sourceFiles.map((file, idx) => (
                              <div
                                key={idx}
                                className="bg-white border border-gray-400 px-2 py-1 text-xs font-mono"
                              >
                                {file}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {insight.affectedStudents.length > 1 && (
                        <div>
                          <div className="text-xs font-bold mb-1">
                            Affected Students
                          </div>
                          <div className="text-xs text-gray-600">
                            {insight.affectedStudents.length} students involved
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="border-2 border-gray-400 p-4">
        <div className="font-bold mb-2 text-sm">[!] Important Note</div>
        <p className="text-xs text-gray-600">
          AI suggestions are supportive. The final assessment always remains the
          responsibility of the lecturer.
        </p>
      </div>
    </div>
  );
}
