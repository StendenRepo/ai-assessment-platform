// Transient live-subtitle capture for FR-06 (additive, best-effort).
//
// Runs ALONGSIDE the existing MediaRecorder — it taps the SAME getUserMedia
// stream via the Web Audio API, windows the raw PCM into short self-contained
// WAV chunks, and streams them to the backend WebSocket for on-premise
// transcription. It NEVER reroutes or replaces MediaRecorder, never persists
// anything, and swallows all failures so the recording is never affected.
//
// On-premise/GDPR: audio goes only to our own backend WS -> local STT container.
// The browser Web Speech API is deliberately NOT used.

import { getToken } from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Whisper works best on 16 kHz mono. ~3.5 s windows give the model more context
// per chunk (better accuracy) at a small latency cost.
const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SECONDS = 3.5;

function buildLiveUrl(assessmentId, language) {
  const wsBase = API_URL.replace(/^http/i, 'ws');
  const token = getToken();
  const params = new URLSearchParams();
  if (token) params.set('token', token);
  if (language) params.set('language', language);
  return `${wsBase}/api/v1/assessments/${assessmentId}/recording/live?${params.toString()}`;
}

// Average-downsample a Float32 PCM buffer from inRate to outRate.
function downsample(buffer, inRate, outRate) {
  if (outRate >= inRate) return buffer;
  const ratio = inRate / outRate;
  const newLen = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLen);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < newLen) {
    const nextOffset = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffset && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffset;
  }
  return result;
}

// Encode mono Float32 PCM as a self-contained 16-bit WAV ArrayBuffer.
function encodeWav(float32, sampleRate) {
  const bytesPerSample = 2;
  const dataSize = float32.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);
  const writeStr = (off, str) => {
    for (let i = 0; i < str.length; i++)
      view.setUint8(off + i, str.charCodeAt(i));
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true); // byte rate
  view.setUint16(32, bytesPerSample, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, 'data');
  view.setUint32(40, dataSize, true);
  let off = 44;
  for (let i = 0; i < float32.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

/**
 * Create a live-subtitle session.
 *
 * @param {object} opts
 * @param {string} opts.assessmentId
 * @param {string} [opts.language]      ISO code ("en"/"nl"); omit to auto-detect
 * @param {(text: string) => void} [opts.onText]   called with each partial text
 * @param {() => void} [opts.onClose]   called once when the session ends/fails
 * @returns {{ start: (stream: MediaStream) => void, stop: () => void }}
 */
export function createLiveSubtitleSession({
  assessmentId,
  language,
  onText,
  onClose,
}) {
  let ws = null;
  let audioContext = null;
  let sourceNode = null;
  let processorNode = null;
  let muteGain = null;
  let pending = [];
  let pendingLength = 0;
  let closed = false;
  let paused = false;

  function finish() {
    if (closed) return;
    closed = true;
    try {
      processorNode && (processorNode.onaudioprocess = null);
      processorNode && processorNode.disconnect();
      sourceNode && sourceNode.disconnect();
      muteGain && muteGain.disconnect();
      audioContext && audioContext.close();
    } catch {
      /* best-effort teardown */
    }
    try {
      ws && ws.readyState <= WebSocket.OPEN && ws.close();
    } catch {
      /* already closing */
    }
    pending = [];
    pendingLength = 0;
    onClose && onClose();
  }

  function flush() {
    if (pendingLength === 0) return;
    const merged = new Float32Array(pendingLength);
    let offset = 0;
    for (const part of pending) {
      merged.set(part, offset);
      offset += part.length;
    }
    pending = [];
    pendingLength = 0;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(encodeWav(merged, TARGET_SAMPLE_RATE));
      } catch {
        /* drop this chunk; live is best-effort */
      }
    }
  }

  function start(stream) {
    try {
      ws = new WebSocket(buildLiveUrl(assessmentId, language));
      ws.binaryType = 'arraybuffer';
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg && msg.type === 'partial' && msg.text)
            onText && onText(msg.text);
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onerror = finish;
      ws.onclose = finish;

      const Ctx = window.AudioContext || window.webkitAudioContext;
      audioContext = new Ctx();
      sourceNode = audioContext.createMediaStreamSource(stream);
      // ScriptProcessor is deprecated but universally supported and adequate for
      // a best-effort transient feature. Route through a zero-gain node so the
      // mic is never played back through the speakers (no echo).
      processorNode = audioContext.createScriptProcessor(4096, 1, 1);
      muteGain = audioContext.createGain();
      muteGain.gain.value = 0;

      const inRate = audioContext.sampleRate;
      const chunkSamples = TARGET_SAMPLE_RATE * CHUNK_SECONDS;

      processorNode.onaudioprocess = (e) => {
        if (closed || paused) return;
        const input = e.inputBuffer.getChannelData(0);
        const down = downsample(input, inRate, TARGET_SAMPLE_RATE);
        // copy: the input buffer is reused by the audio engine after this call
        pending.push(new Float32Array(down));
        pendingLength += down.length;
        if (pendingLength >= chunkSamples) flush();
      };

      sourceNode.connect(processorNode);
      processorNode.connect(muteGain);
      muteGain.connect(audioContext.destination);
    } catch {
      // Any setup failure -> silently give up; recording continues unaffected.
      finish();
    }
  }

  function stop() {
    // Intentionally do NOT flush a final partial window — a tiny tail chunk adds
    // latency for little value. Just tear everything down.
    finish();
  }

  // Pause/resume the live capture in step with MediaRecorder. While paused we
  // skip capturing and drop any buffered audio so a stale window isn't sent on
  // resume. The WebSocket stays open so resume is instant.
  function setPaused(value) {
    paused = value;
    if (value) {
      pending = [];
      pendingLength = 0;
    }
  }

  return { start, stop, setPaused };
}
