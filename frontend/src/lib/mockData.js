export const mockContributions = [
  {
    id: 'contrib-1',
    type: 'code',
    title: 'Frontend Authentication Module',
    description:
      'Implementation of login, registration and password reset functionality',
    evidenceFiles: [
      {
        id: 'ev-1',
        fileName: 'auth.tsx',
        fileType: 'code',
        excerpt: 'const handleLogin = async (credentials) => {...}',
        sourceUrl: 'github.com/project/auth.tsx',
        uploadDate: '2026-05-10',
      },
      {
        id: 'ev-2',
        fileName: 'auth-tests.spec.ts',
        fileType: 'code',
        excerpt: 'describe("Authentication", () => {...})',
        sourceUrl: 'github.com/project/auth-tests.spec.ts',
        uploadDate: '2026-05-11',
      },
    ],
    linkedCriteria: ['crit-1', 'crit-4'],
    timestamp: '2026-05-10T14:30:00',
    aiConfidence: 0.92,
  },
  {
    id: 'contrib-2',
    type: 'documentation',
    title: 'API Documentation',
    description: 'Complete documentation of all REST endpoints with examples',
    evidenceFiles: [
      {
        id: 'ev-3',
        fileName: 'API-docs.md',
        fileType: 'markdown',
        excerpt: '## Authentication Endpoints\n\n### POST /api/login...',
        sourceUrl: 'github.com/project/docs/API-docs.md',
        uploadDate: '2026-05-12',
      },
    ],
    linkedCriteria: ['crit-2'],
    timestamp: '2026-05-12T10:15:00',
    aiConfidence: 0.88,
  },
  {
    id: 'contrib-3',
    type: 'presentation',
    title: 'Sprint Demo Presentation',
    description: 'Preparation and delivery of final presentation',
    evidenceFiles: [
      {
        id: 'ev-4',
        fileName: 'demo-slides.pdf',
        fileType: 'pdf',
        sourceUrl: 'drive.google.com/demo-slides.pdf',
        uploadDate: '2026-05-14',
      },
    ],
    linkedCriteria: ['crit-5'],
    timestamp: '2026-05-14T16:00:00',
    aiConfidence: 0.75,
  },
];

export const mockCriteria = [
  {
    id: 'crit-1',
    name: 'Code Quality',
    description: 'Readable, maintainable and well-structured code',
    maxScore: 10,
    category: 'Technical',
  },
  {
    id: 'crit-2',
    name: 'Documentation',
    description: 'Completeness and clarity of technical documentation',
    maxScore: 10,
    category: 'Communication',
  },
  {
    id: 'crit-3',
    name: 'Collaboration',
    description: 'Contribution to teamwork and communication',
    maxScore: 10,
    category: 'Process',
  },
  {
    id: 'crit-4',
    name: 'Testing',
    description: 'Unit tests, integration tests and test coverage',
    maxScore: 10,
    category: 'Technical',
  },
  {
    id: 'crit-5',
    name: 'Presentation',
    description: 'Oral presentation and communication skills',
    maxScore: 10,
    category: 'Communication',
  },
];

export const mockAIInsights = [
  {
    id: 'insight-1',
    type: 'overlap',
    severity: 'high',
    title: 'Possible duplicate claim: Authentication Module',
    description:
      'Two students claim the same contribution to the authentication module. Review recommended.',
    affectedStudents: ['student-1', 'student-2'],
    evidence: ['ev-1', 'ev-2'],
    sourceFiles: ['auth.tsx', 'auth-tests.spec.ts'],
  },
  {
    id: 'insight-2',
    type: 'suggestion',
    severity: 'medium',
    title: 'Insufficient evidence for documentation claim',
    description:
      'Student claims documentation work, but only 1 file found. Evidence may be missing.',
    affectedStudents: ['student-3'],
    evidence: [],
    sourceFiles: [],
  },
  {
    id: 'insight-3',
    type: 'anomaly',
    severity: 'low',
    title: 'Unusual commit pattern',
    description:
      'All commits for this student were made between 11PM-4AM. Possibly no issue, but notable pattern.',
    affectedStudents: ['student-4'],
    evidence: [],
    sourceFiles: ['Multiple files'],
  },
];
