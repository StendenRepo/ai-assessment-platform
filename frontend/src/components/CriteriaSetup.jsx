'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { mockCriteria } from '@/lib/mockData';

const CATEGORIES = ['Technical', 'Communication', 'Process', 'Collaboration'];

export default function CriteriaSetup({ projectId }) {
  const router = useRouter();
  const [criteria, setCriteria] = useState(mockCriteria);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newCriterion, setNewCriterion] = useState({
    name: '',
    description: '',
    maxScore: 10,
    category: 'Technical',
  });

  const handleAddCriterion = () => {
    setCriteria([...criteria, { id: `crit-${Date.now()}`, ...newCriterion }]);
    setShowAddForm(false);
    setNewCriterion({
      name: '',
      description: '',
      maxScore: 10,
      category: 'Technical',
    });
  };

  return (
    <div>
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">
          Setup Assessment Criteria &amp; Rubrics
        </h2>
        <p className="text-gray-600">
          Define the criteria and rubrics for assessing this project
        </p>
      </div>

      <div className="max-w-5xl space-y-6">
        <div className="border-2 border-gray-400 p-6 bg-gray-50">
          <h3 className="font-bold mb-4">Import Existing Rubric (Optional)</h3>
          <div className="flex gap-4">
            <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100">
              [IMPORT FROM FILE]
            </button>
            <button className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100">
              [LOAD TEMPLATE]
            </button>
          </div>
          <div className="text-sm text-gray-600 mt-3">
            Or create criteria manually below
          </div>
        </div>

        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold">Assessment Criteria</h3>
          <button
            onClick={() => setShowAddForm(true)}
            className="border-2 border-gray-400 bg-gray-900 text-white px-4 py-2 hover:bg-gray-700"
          >
            [+ ADD CRITERION]
          </button>
        </div>

        {showAddForm && (
          <div className="border-2 border-gray-400 p-6 bg-gray-50">
            <h3 className="font-bold mb-4">New Criterion</h3>
            <div className="space-y-4">
              <div>
                <label className="block font-bold mb-2">Name *</label>
                <input
                  type="text"
                  value={newCriterion.name}
                  onChange={(e) =>
                    setNewCriterion({ ...newCriterion, name: e.target.value })
                  }
                  className="w-full border-2 border-gray-400 px-4 py-2"
                  placeholder="e.g. Code Quality"
                />
              </div>
              <div>
                <label className="block font-bold mb-2">Description *</label>
                <textarea
                  value={newCriterion.description}
                  onChange={(e) =>
                    setNewCriterion({
                      ...newCriterion,
                      description: e.target.value,
                    })
                  }
                  rows={3}
                  className="w-full border-2 border-gray-400 px-4 py-2"
                  placeholder="Describe what will be assessed..."
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-bold mb-2">Category *</label>
                  <select
                    value={newCriterion.category}
                    onChange={(e) =>
                      setNewCriterion({
                        ...newCriterion,
                        category: e.target.value,
                      })
                    }
                    className="w-full border-2 border-gray-400 px-4 py-2"
                  >
                    {CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-bold mb-2">
                    Maximum Score *
                  </label>
                  <input
                    type="number"
                    value={newCriterion.maxScore}
                    onChange={(e) =>
                      setNewCriterion({
                        ...newCriterion,
                        maxScore: parseInt(e.target.value),
                      })
                    }
                    className="w-full border-2 border-gray-400 px-4 py-2"
                    min="1"
                    max="100"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowAddForm(false)}
                  className="border-2 border-gray-400 px-4 py-2 hover:bg-gray-100"
                >
                  [CANCEL]
                </button>
                <button
                  onClick={handleAddCriterion}
                  className="border-2 border-gray-400 bg-gray-900 text-white px-4 py-2"
                >
                  [SAVE]
                </button>
              </div>
            </div>
          </div>
        )}

        <div>
          <div className="text-sm text-gray-600 mb-4">
            Total criteria: {criteria.length} | Total points:{' '}
            {criteria.reduce((sum, c) => sum + c.maxScore, 0)}
          </div>

          {CATEGORIES.map((category) => {
            const categoryCriteria = criteria.filter(
              (c) => c.category === category
            );
            if (categoryCriteria.length === 0) return null;
            return (
              <div key={category} className="mb-6">
                <div className="bg-gray-200 border-2 border-gray-400 px-4 py-2 font-bold mb-2">
                  [{category.toUpperCase()}] ({categoryCriteria.length})
                </div>
                <div className="space-y-2">
                  {categoryCriteria.map((criterion) => (
                    <div
                      key={criterion.id}
                      className="border-2 border-gray-400 p-4"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <h4 className="font-bold">{criterion.name}</h4>
                            <span className="text-sm border border-gray-400 px-2 py-1">
                              Max: {criterion.maxScore} points
                            </span>
                          </div>
                          <p className="text-sm text-gray-600">
                            {criterion.description}
                          </p>
                        </div>
                        <button
                          onClick={() =>
                            setCriteria(
                              criteria.filter((c) => c.id !== criterion.id)
                            )
                          }
                          className="border-2 border-gray-400 px-3 py-1 text-sm hover:bg-gray-100 ml-4"
                        >
                          [DELETE]
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex gap-4 justify-end pt-6 border-t-2 border-gray-300">
          <button className="border-2 border-gray-400 px-6 py-3 hover:bg-gray-100">
            [SAVE AS DRAFT]
          </button>
          <button
            onClick={() => router.push('/dashboard')}
            className="border-2 border-gray-400 bg-gray-900 text-white px-6 py-3 hover:bg-gray-700"
          >
            [COMPLETE PROJECT SETUP →]
          </button>
        </div>
      </div>
    </div>
  );
}
