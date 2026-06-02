const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function req(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail ?? err.error ?? res.statusText;
    throw new Error(
      typeof detail === 'string' ? detail : JSON.stringify(detail)
    );
  }
  if (res.headers.get('content-type')?.includes('application/json')) {
    return res.json();
  }
  return res;
}

/** Dev projectId → moduleId, groupId → projectId */
function mod(projectId) {
  return `/api/v1/modules/${projectId}`;
}

export const platformApi = {
  // --- Module / project ---
  listModules: () => req('/api/v1/modules'),

  createModule: (name, academicYear) =>
    req('/api/v1/modules', {
      method: 'POST',
      body: JSON.stringify({ name, academic_year: academicYear }),
    }),

  getModule: (projectId) => req(`${mod(projectId)}`),

  uploadRubric: (projectId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return req(`${mod(projectId)}/rubric`, { method: 'POST', body: fd });
  },

  uploadModuleGuide: (projectId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return req(`${mod(projectId)}/module-guide`, {
      method: 'POST',
      body: fd,
    });
  },

  removeRubric: (projectId) =>
    req(`${mod(projectId)}/rubric`, { method: 'DELETE' }),

  removeModuleGuide: (projectId) =>
    req(`${mod(projectId)}/module-guide`, { method: 'DELETE' }),

  createGroup: (projectId, name) =>
    req(`${mod(projectId)}/groups`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  getGroup: (projectId, groupId) =>
    req(`${mod(projectId)}/projects/${groupId}`),

  addStudent: (projectId, groupId, name, studentNumber) =>
    req(`${mod(projectId)}/projects/${groupId}/students`, {
      method: 'POST',
      body: JSON.stringify({ name, student_number: studentNumber }),
    }),

  removeStudent: (projectId, groupId, studentId) =>
    req(`${mod(projectId)}/projects/${groupId}/students/${studentId}`, {
      method: 'DELETE',
    }),

  uploadEvidence: (projectId, groupId, studentId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return req(
      `${mod(projectId)}/projects/${groupId}/students/${studentId}/evidence`,
      { method: 'POST', body: fd }
    );
  },

  removeEvidence: (projectId, groupId, studentId, evidenceId) =>
    req(
      `${mod(projectId)}/projects/${groupId}/students/${studentId}/evidence/${evidenceId}`,
      { method: 'DELETE' }
    ),

  // --- Analysis ---
  ensureGroup: (projectId, groupId) =>
    req(`/api/v1/modules/${projectId}/projects/${groupId}/ensure`, {
      method: 'POST',
    }),

  startAnalysis: (projectId, groupId) =>
    req(`${mod(projectId)}/projects/${groupId}/analyze`, { method: 'POST' }),

  analysisStatus: (projectId, groupId) =>
    req(`${mod(projectId)}/projects/${groupId}/analyze/status`),

  async runAnalysis(projectId, groupId, onProgress) {
    await platformApi.startAnalysis(projectId, groupId);
    const poll = async () => {
      const s = await platformApi.analysisStatus(projectId, groupId);
      onProgress?.(s);
      if (s.status === 'completed') return s;
      if (s.status === 'failed') throw new Error(s.error || 'Analysis failed');
      await new Promise((r) => setTimeout(r, 450));
      return poll();
    };
    return poll();
  },

  getInsights: (projectId, groupId, studentId) =>
    req(
      `/api/v1/modules/${projectId}/projects/${groupId}/students/${studentId}/ai-insights`
    ),

  getStudentWorkspace: (projectId, groupId, studentId) =>
    req(`${mod(projectId)}/projects/${groupId}/students/${studentId}`),

  updateDraft: (projectId, groupId, studentId, draftForm) =>
    req(`${mod(projectId)}/projects/${groupId}/students/${studentId}/draft`, {
      method: 'PATCH',
      body: JSON.stringify(draftForm),
    }),

  recordConsent: (projectId, groupId, studentId, consentGiven, note = '') =>
    req(`${mod(projectId)}/projects/${groupId}/students/${studentId}/consent`, {
      method: 'POST',
      body: JSON.stringify({ consent_given: consentGiven, note }),
    }),

  uploadTranscript: (projectId, groupId, studentId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return req(
      `${mod(projectId)}/projects/${groupId}/students/${studentId}/transcript`,
      { method: 'POST', body: fd }
    );
  },

  chat: (projectId, groupId, studentId, message) =>
    req(`${mod(projectId)}/projects/${groupId}/students/${studentId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  async chatStream(
    projectId,
    groupId,
    studentId,
    message,
    { onToken, onDone, onError } = {}
  ) {
    const res = await fetch(
      `${API}${mod(projectId)}/projects/${groupId}/students/${studentId}/chat/stream`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      const msg = err.detail || err.error || res.statusText;
      onError?.(msg);
      throw new Error(msg);
    }
    if (!res.body) {
      onError?.('No response stream');
      throw new Error('No response stream');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const handleBlock = (block) => {
      let event = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      if (!data) return;
      const payload = JSON.parse(data);
      if (event === 'token') onToken?.(payload.text ?? '');
      else if (event === 'done') onDone?.(payload);
      else if (event === 'error') onError?.(payload.message ?? 'Stream error');
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        if (block.trim()) handleBlock(block);
      }
    }
    if (buffer.trim()) handleBlock(buffer);
  },

  chatHistory: (projectId, groupId, studentId) =>
    req(`${mod(projectId)}/projects/${groupId}/students/${studentId}/chat`),

  exportZipUrl: (projectId, groupId, studentId) =>
    `${API}${mod(projectId)}/projects/${groupId}/students/${studentId}/export/zip`,

  exportEmlUrl: (projectId, groupId, studentId) =>
    `${API}${mod(projectId)}/projects/${groupId}/students/${studentId}/export/eml`,

  audit: (params = {}) => {
    const sp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') sp.set(k, String(v));
    });
    const qs = sp.toString();
    return req(`/api/v1/audit${qs ? `?${qs}` : ''}`);
  },

  llmStatus: () => req('/api/v1/llm-status'),

  seedDemo: () => req('/api/v1/seed-demo', { method: 'POST' }),
};
