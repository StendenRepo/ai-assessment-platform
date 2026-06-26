"""On-premise AI-generated text classifier (RoBERTa fine-tuned for detection).

Unlike general-purpose LLMs (Llama, Qwen), this service uses a dedicated
binary classifier trained to distinguish human vs machine-written text.

Document score uses word-level coverage (like GPTZero %), not the single
highest-scoring window — so mixed human/AI essays are not reported as 99% AI.
"""
from __future__ import annotations

import os
import re
import statistics

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Hello-SimpleAI: trained on HC3 human vs ChatGPT pairs; separates casual human voice
# from templated prose better than AIGC_detector_env3 for student essays.
MODEL_NAME = os.getenv("AI_DETECTOR_MODEL", "Hello-SimpleAI/chatgpt-detector-roberta")
DEVICE = os.getenv("AI_DETECTOR_DEVICE", "cpu")
MAX_LENGTH = int(os.getenv("AI_DETECTOR_MAX_TOKENS", "512"))
WINDOW_WORDS = int(os.getenv("AI_DETECTOR_WINDOW_WORDS", "80"))
STRIDE_WORDS = int(os.getenv("AI_DETECTOR_STRIDE_WORDS", "40"))
MIN_WORDS = int(os.getenv("AI_DETECTOR_MIN_WORDS", "30"))
SEGMENT_FLAG_MIN = float(os.getenv("AI_DETECTOR_SEGMENT_MIN", "0.55"))
MEDIAN_MARGIN = float(os.getenv("AI_DETECTOR_MEDIAN_MARGIN", "0.08"))

app = FastAPI(title="AI Text Detector", version="0.1.0")

_tokenizer: AutoTokenizer | None = None
_model: AutoModelForSequenceClassification | None = None
_ai_label_id: int = 1


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1)


def get_classifier():
    global _tokenizer, _model, _ai_label_id
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        _model.eval()
        _model.to(DEVICE)
        id2label = getattr(_model.config, "id2label", None) or {}
        for idx, label in id2label.items():
            lowered = str(label).lower()
            if any(token in lowered for token in ("ai", "machine", "fake", "generated", "chatgpt")):
                _ai_label_id = int(idx)
                break
    return _tokenizer, _model


def _word_windows(text: str) -> list[tuple[int, int, str]]:
    """Return (start_word, word_count, text) for each sliding window."""
    words = text.split()
    if len(words) <= WINDOW_WORDS:
        return [(0, len(words), text)]

    windows: list[tuple[int, int, str]] = []
    start = 0
    while start < len(words):
        chunk_words = words[start : start + WINDOW_WORDS]
        if len(chunk_words) < 20 and windows:
            break
        windows.append((start, len(chunk_words), " ".join(chunk_words)))
        if start + WINDOW_WORDS >= len(words):
            break
        start += STRIDE_WORDS
    return windows


def _ai_probability(text: str) -> float:
    tokenizer, model = get_classifier()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
        padding=False,
    )
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
    return float(probs[_ai_label_id].item())


def _document_ai_coverage(
    word_count: int,
    windows: list[tuple[int, int, str, float]],
    *,
    threshold: float,
) -> tuple[float, float]:
    """Return (document AI %, peak section %) — fraction of words in AI-like regions."""
    if word_count <= 0:
        return 0.0, 0.0
    word_scores = [0.0] * word_count
    for start, length, _text, prob in windows:
        end = min(start + length, word_count)
        for i in range(start, end):
            word_scores[i] = max(word_scores[i], prob)
    peak = max(word_scores) if word_scores else 0.0
    flagged_words = sum(1 for score in word_scores if score >= threshold)
    document_score = flagged_words / word_count
    if flagged_words == 0:
        document_score = sum(word_scores) / word_count
    return document_score, peak


def _passage_threshold(window_probs: list[float]) -> float:
    if not window_probs:
        return SEGMENT_FLAG_MIN
    median_prob = statistics.median(window_probs)
    return max(SEGMENT_FLAG_MIN, median_prob + MEDIAN_MARGIN)


@app.get("/health")
def health():
    return {"status": "healthy", "model": MODEL_NAME, "device": DEVICE}


@app.post("/classify")
def classify(body: ClassifyRequest):
    clean = re.sub(r"\s+", " ", body.text).strip()
    word_count = len(clean.split())
    if word_count < MIN_WORDS:
        return {
            "available": True,
            "model": MODEL_NAME,
            "ai_probability": 0.0,
            "human_probability": 1.0,
            "label": "human",
            "status": "none",
            "explanation": f"Text too short for classifier ({word_count} words, need {MIN_WORDS}).",
            "segments": [],
            "max_segment_probability": 0.0,
            "ai_window_fraction": 0.0,
        }

    scored_windows: list[tuple[int, int, str, float]] = []
    for start, length, window_text in _word_windows(clean):
        prob = _ai_probability(window_text)
        scored_windows.append((start, length, window_text, prob))

    window_probs = [row[3] for row in scored_windows]
    threshold = _passage_threshold(window_probs)
    ai_probability, peak_segment = _document_ai_coverage(
        word_count, scored_windows, threshold=threshold
    )

    flagged_windows = [row for row in scored_windows if row[3] >= threshold]
    ai_window_fraction = len(flagged_windows) / len(scored_windows)

    segments = [
        {
            "start_word": start,
            "text": window_text[:400],
            "ai_probability": round(prob, 4),
        }
        for start, _length, window_text, prob in sorted(
            flagged_windows, key=lambda row: row[3], reverse=True
        )[:8]
    ]

    human_probability = round(max(0.0, 1.0 - ai_probability), 4)
    label = "ai" if ai_probability >= 0.15 else "human"
    if ai_probability >= 0.40:
        status = "confirmed"
    elif ai_probability >= 0.15:
        status = "possible"
    else:
        status = "none"

    pct = int(round(ai_probability * 100))
    if flagged_windows:
        explanation = (
            f"Classifier ({MODEL_NAME}) estimates ~{pct}% of this submission "
            f"shows AI writing patterns ({len(flagged_windows)} of "
            f"{len(scored_windows)} sections flagged)."
        )
    else:
        explanation = (
            f"Classifier ({MODEL_NAME}) estimates ~{pct}% AI-like content; "
            "no section reached the highlight threshold."
        )

    return {
        "available": True,
        "model": MODEL_NAME,
        "ai_probability": round(ai_probability, 4),
        "human_probability": human_probability,
        "max_segment_probability": round(peak_segment, 4),
        "ai_window_fraction": round(ai_window_fraction, 4),
        "label": label,
        "status": status,
        "explanation": explanation,
        "segments": segments,
    }
