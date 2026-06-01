from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ai.chunker import chunk_text
from app.ai.confidence_scorer import to_suggestion_strength


def match_evidence(
    criterion: str,
    student_name: str,
    source_file: str,
    text: str,
) -> list[dict]:
    chunks = chunk_text(text)
    if not chunks:
        return []

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform([criterion, *chunks])
    scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

    best_idx = int(scores.argmax())
    best_score = float(scores[best_idx])
    quote = chunks[best_idx]
    if len(quote) > 220:
        quote = quote[:217] + "..."

    return [
        {
            "student": student_name,
            "source_file": source_file,
            "criterion": criterion,
            "suggestion_strength": to_suggestion_strength(best_score),
            "similarity": round(best_score, 4),
            "quote": quote,
        }
    ]
