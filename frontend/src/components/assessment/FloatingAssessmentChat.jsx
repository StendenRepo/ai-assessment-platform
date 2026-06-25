'use client';

import { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { MessageSquare, X } from 'lucide-react';
import AssessmentChatWidget from './AssessmentChatWidget';

const FloatingAssessmentChat = forwardRef(function FloatingAssessmentChat(
  { assessmentId, disabled = false, canChat = true, onDraftUpdated, onApplied },
  ref
) {
  const [open, setOpen] = useState(false);
  const chatRef = useRef(null);

  useImperativeHandle(ref, () => ({
    open() {
      setOpen(true);
    },
    focusCriterion(criterionKey, criterionName, score) {
      setOpen(true);
      requestAnimationFrame(() => {
        chatRef.current?.focusCriterion(criterionKey, criterionName, score);
      });
    },
  }));

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {open && (
        <div
          className="absolute bottom-16 right-0 w-[min(380px,calc(100vw-2rem))] shadow-2xl rounded-lg overflow-hidden origin-bottom-right transition-all duration-200 scale-100 opacity-100"
          role="dialog"
          aria-label="Discuss with AI"
        >
          <AssessmentChatWidget
            ref={chatRef}
            assessmentId={assessmentId}
            disabled={disabled}
            canChat={canChat}
            onDraftUpdated={onDraftUpdated}
            onApplied={onApplied}
            className="h-[min(520px,calc(100vh-8rem))] max-h-[min(560px,calc(100vh-8rem))]"
          />
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label={open ? 'Close AI chat' : 'Open AI chat'}
        aria-expanded={open}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors cursor-pointer"
      >
        {open ? <X size={22} /> : <MessageSquare size={22} />}
      </button>
    </div>
  );
});

export default FloatingAssessmentChat;
