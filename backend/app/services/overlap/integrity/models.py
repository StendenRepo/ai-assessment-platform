"""Shared data contracts for academic-integrity detection results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IntegrityFlag:
    flag_type: str  # "ai" or "student"
    confidence: float
    reason: str
    text: str = ""
    text_a: str = ""
    text_b: str = ""
    match_id: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "type": self.flag_type,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
        }
        if self.text:
            payload["text"] = self.text
        if self.text_a:
            payload["text_a"] = self.text_a
        if self.text_b:
            payload["text_b"] = self.text_b
        if self.match_id is not None:
            payload["match_id"] = self.match_id
        return payload


@dataclass
class IntegrityResult:
    integrity_type: str  # "ai", "student_plagiarism", "both", "none"
    confidence: float
    status: str  # "confirmed", "possible", "none"
    flags: list[IntegrityFlag] = field(default_factory=list)
    explanation: str = ""
    ai_verified: bool = False
    detection_method: str = "statistical"

    def to_dict(self) -> dict:
        return {
            "integrity_type": self.integrity_type,
            "confidence": round(self.confidence, 4),
            "status": self.status,
            "flags": [f.to_dict() for f in self.flags],
            "explanation": self.explanation,
            "ai_verified": self.ai_verified,
            "detection_method": self.detection_method,
        }
