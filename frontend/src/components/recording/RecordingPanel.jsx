'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Mic,
  Square,
  Shield,
  Loader2,
  CheckCircle2,
  XCircle,
  Trash2,
} from 'lucide-react';
import {
  getRecordingState,
  uploadRecording,
  setConsent as apiSetConsent,
} from '@/lib/recording';
import ConsentBadge from '@/components/recording/ConsentBadge';

/**
 * Full recording + oral-consent flow for an individual assessment (FR-06).
 *
 * Flow: the teacher records audio (G2-136). The student's spoken name + "I
 * consent" is the first thing captured (G2-137). After stopping, the audio is
 * uploaded and transcribed on-premise (G2-140); the teacher reviews the opening
 * of the transcript and confirms Accept / Decline, which drives the consent
 * indicator (G2-138). A declined assessment proceeds without audio.
 */
export default function RecordingPanel({
  assessmentId,
  backendEnabled = true,
}) {
  const [state, setState] = useState(null); // backend RecordingStateOut
  const [error, setError] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const pollRef = useRef(null);

  // Load current recording/consent state on mount.
  useEffect(() => {
    if (!backendEnabled) return;

    let active = true;
    getRecordingState(assessmentId)
      .then((s) => active && setState(s))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [assessmentId, backendEnabled]);

  // Recording timer.
  useEffect(() => {
    if (isRecording) {
      timerRef.current = setInterval(() => setElapsed((t) => t + 1), 1000);
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    return () => timerRef.current && clearInterval(timerRef.current);
  }, [isRecording]);

  // Poll while transcription is in progress.
  useEffect(() => {
    if (!backendEnabled) return;

    const status = state?.transcription_status;
    if (status === 'pending' || status === 'processing') {
      pollRef.current = setInterval(async () => {
        try {
          const s = await getRecordingState(assessmentId);
          setState(s);
          if (
            s.transcription_status !== 'pending' &&
            s.transcription_status !== 'processing'
          ) {
            clearInterval(pollRef.current);
          }
        } catch {
          /* keep polling */
        }
      }, 3000);
      return () => pollRef.current && clearInterval(pollRef.current);
    }
  }, [state?.transcription_status, assessmentId, backendEnabled]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      pollRef.current && clearInterval(pollRef.current);
    };
  }, []);

  const formatTime = (s) =>
    `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

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

    if (!backendEnabled) {
      setState({
        assessment_id: assessmentId ?? 'local',
        has_recording: true,
        consent_status: 'pending',
        transcription_status: 'completed',
        transcript_text: null,
        delete_after: null,
        flagged_for_deletion: false,
      });
      setError(null);
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const s = await uploadRecording(assessmentId, blob);
      setState(s); // transcription_status will be pending -> poller takes over
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  async function decide(status) {
    setSavingConsent(true);
    setError(null);
    try {
      if (!backendEnabled) {
        setState((current) => ({
          ...(current ?? {
            assessment_id: assessmentId ?? 'local',
            has_recording: false,
            transcription_status: 'completed',
            transcript_text: null,
            delete_after: null,
            flagged_for_deletion: false,
          }),
          consent_status: status,
          consent_confirmed_at: new Date().toISOString(),
        }));
        return;
      }

      const s = await apiSetConsent(assessmentId, status);
      setState(s);
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingConsent(false);
    }
  }

  const transcribing =
    state?.transcription_status === 'pending' ||
    state?.transcription_status === 'processing';
  const transcriptReady = state?.transcription_status === 'completed';
  const consentPending = state?.consent_status === 'pending';

  return (
    <div className="rounded-lg bg-card border border-border p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Recording &amp; Consent
        </h3>
        {state && <ConsentBadge status={state.consent_status} />}
      </div>

      {error && (
        <div className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      {!backendEnabled && (
        <div className="rounded-md bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-300">
          Demo mode: this page is using mock student data, so recordings are not
          uploaded or transcribed until the student is linked to a real backend
          assessment.
        </div>
      )}

      {/* Oral consent instruction (G2-137) */}
      {!state?.has_recording && !isRecording && (
        <div className="rounded-md bg-secondary border border-border p-3 text-[11px] text-muted-foreground leading-relaxed">
          At the start of the recording, ask the student to state their full
          name and say{' '}
          <span className="font-semibold text-foreground">
            &ldquo;I consent&rdquo;
          </span>
          . You will confirm their decision after reviewing the transcript.
        </div>
      )}

      {/* Recorder controls (G2-136) */}
      {!state?.has_recording && (
        <div className="space-y-3">
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
          ) : (
            state?.consent_status !== 'declined' && (
              <div className="space-y-2">
                <button
                  onClick={startRecording}
                  disabled={uploading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  <Mic size={15} /> Start Recording
                </button>
                <button
                  onClick={() => decide('declined')}
                  disabled={savingConsent || uploading}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md border border-border text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-50"
                >
                  <XCircle size={13} /> Student declined — proceed without
                  recording
                </button>
              </div>
            )
          )}
        </div>
      )}

      {uploading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 size={14} className="animate-spin" /> Uploading recording…
        </div>
      )}

      {/* Transcription status / review (G2-140) */}
      {state?.has_recording && (
        <div className="space-y-3">
          {transcribing && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 size={14} className="animate-spin" /> Transcribing
              recording…
            </div>
          )}
          {state.transcription_status === 'failed' && (
            <div className="rounded-md bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-400">
              Transcription failed. The recording is saved; you can still
              confirm consent manually.
            </div>
          )}
          {transcriptReady && (
            <div>
              <p className="text-[10px] font-semibold text-foreground mb-1.5 uppercase tracking-wide">
                Transcript (consent stated at the start)
              </p>
              <div className="rounded bg-background border border-border px-3 py-2 text-xs text-muted-foreground max-h-40 overflow-y-auto whitespace-pre-wrap">
                {state.transcript_text || '(empty transcript)'}
              </div>
            </div>
          )}

          {/* Teacher confirms oral consent (G2-137, G2-138) */}
          {consentPending && (
            <div className="space-y-2">
              <p className="text-[11px] text-muted-foreground">
                Did the student give consent to record?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => decide('accepted')}
                  disabled={savingConsent}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20 text-sm font-semibold hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  <CheckCircle2 size={14} /> Accept
                </button>
                <button
                  onClick={() => decide('declined')}
                  disabled={savingConsent}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-red-500/10 text-red-400 ring-1 ring-red-500/20 text-sm font-semibold hover:bg-red-500/20 transition-colors disabled:opacity-50"
                >
                  <XCircle size={14} /> Decline
                </button>
              </div>
            </div>
          )}

          {/* Retention info (G2-141 / G2-142) */}
          {state.delete_after && (
            <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
              <Trash2
                size={12}
                className="text-muted-foreground mt-0.5 shrink-0"
              />
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {state.flagged_for_deletion
                  ? 'This recording is flagged for deletion.'
                  : `Scheduled for deletion on ${new Date(state.delete_after).toLocaleDateString()}.`}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Declined: assessment proceeds without audio */}
      {state?.consent_status === 'declined' && !state?.has_recording && (
        <div className="rounded-md bg-secondary border border-border p-3 text-[11px] text-muted-foreground leading-relaxed">
          Recording declined. The assessment proceeds without audio.
        </div>
      )}

      <div className="flex items-start gap-2 rounded-md bg-secondary border border-border p-3">
        <Shield size={12} className="text-muted-foreground mt-0.5 shrink-0" />
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          Recording stored securely on-premises (GDPR). Transcription is
          descriptive only and never produces grades.
        </p>
      </div>
    </div>
  );
}
