'use client';

import { useEffect, useRef, useState } from 'react';
import { Mic, Square, Shield, Loader2, Plus } from 'lucide-react';
import {
  getConsentState,
  setConsent as apiSetConsent,
  listRecordings,
  appendRecording,
} from '@/lib/recording';
import ConsentBadge from '@/components/recording/ConsentBadge';
import ConsentPromptDialog from '@/components/recording/ConsentPromptDialog';
import RecordingRow from '@/components/recording/RecordingRow';

/**
 * Multi-recording panel for an individual assessment (FR-06).
 *
 * Consent is confirmed BEFORE EVERY recording (G2-137): clicking Start / New
 * Recording opens a consent prompt; Accept begins recording (and records a fresh
 * consent decision), Decline cancels that recording. Each recording has its own
 * file, transcript, status and expiry.
 */
export default function RecordingPanel({
  assessmentId,
  backendEnabled = true,
}) {
  const [consent, setConsent] = useState(null); // ConsentStateOut (for the badge)
  const [recordings, setRecordings] = useState([]);
  const [error, setError] = useState(null);
  const [showConsent, setShowConsent] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [uploading, setUploading] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const pollRef = useRef(null);

  async function refresh() {
    const [c, recs] = await Promise.all([
      getConsentState(assessmentId),
      listRecordings(assessmentId),
    ]);
    setConsent(c);
    setRecordings(recs);
    return recs;
  }

  // Initial load.
  useEffect(() => {
    if (!backendEnabled) return;
    let active = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh().catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assessmentId, backendEnabled]);

  // Poll while any recording is still transcribing.
  useEffect(() => {
    const anyPending = recordings.some(
      (r) =>
        r.transcription_status === 'pending' ||
        r.transcription_status === 'processing'
    );
    if (!anyPending) return;
    pollRef.current = setInterval(() => {
      listRecordings(assessmentId)
        .then(setRecordings)
        .catch(() => {});
    }, 3000);
    return () => pollRef.current && clearInterval(pollRef.current);
  }, [recordings, assessmentId]);

  // Recording timer.
  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => setElapsed((t) => t + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [isRecording]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      pollRef.current && clearInterval(pollRef.current);
    };
  }, []);

  const formatTime = (s) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  // Accept in the per-recording prompt: record a fresh consent decision (so the
  // backend allows the upload + leaves an audit trail), then start recording.
  async function acceptConsentAndRecord() {
    const c = await apiSetConsent(assessmentId, 'accepted');
    setConsent(c);
    setShowConsent(false);
    await startRecording();
  }

  function declineConsent() {
    setShowConsent(false); // cancel — nothing recorded
  }

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) =>
        e.data.size > 0 && chunksRef.current.push(e.data);
      recorder.onstop = handleStop;
      mediaRecorderRef.current = recorder;
      recorder.start();
      setElapsed(0);
      setIsRecording(true);
    } catch {
      setError(
        'Microphone access denied. Please allow microphone access to record.'
      );
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  }

  async function handleStop() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
    setUploading(true);
    setError(null);
    try {
      await appendRecording(assessmentId, blob);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="rounded-lg bg-card border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Recordings &amp; Consent
        </h3>
        {consent && <ConsentBadge status={consent.consent_status} />}
      </div>

      {error && (
        <div className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {recordings.length === 0 && !isRecording && (
          <p className="text-[11px] text-muted-foreground">
            No recordings yet. Consent is confirmed each time you start a
            recording.
          </p>
        )}

        {recordings.map((r) => (
          <RecordingRow
            key={r.id}
            assessmentId={assessmentId}
            recording={r}
            onChanged={() => refresh().catch((e) => setError(e.message))}
            onError={setError}
          />
        ))}

        {isRecording ? (
          <div className="rounded-lg bg-red-500/5 border border-red-500/20 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs font-semibold text-red-400 uppercase tracking-wide">
                Recording
              </span>
              <span className="ml-auto text-lg font-bold text-foreground font-mono">
                {formatTime(elapsed)}
              </span>
            </div>
            <button
              onClick={stopRecording}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-foreground text-background text-sm font-semibold hover:bg-foreground/90 transition-colors"
            >
              <Square size={14} /> Stop &amp; Save
            </button>
          </div>
        ) : uploading ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 size={14} className="animate-spin" /> Uploading recording…
          </div>
        ) : (
          <button
            onClick={() => setShowConsent(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
          >
            {recordings.length === 0 ? <Mic size={15} /> : <Plus size={15} />}
            {recordings.length === 0 ? 'Start Recording' : 'New Recording'}
          </button>
        )}
      </div>

      <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
        <Shield size={12} className="text-muted-foreground mt-0.5 shrink-0" />
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Recordings stored securely on-premises (GDPR). Transcription is
          descriptive only and never produces grades.
        </p>
      </div>

      {showConsent && (
        <ConsentPromptDialog
          onAccept={acceptConsentAndRecord}
          onDecline={declineConsent}
        />
      )}
    </div>
  );
}
