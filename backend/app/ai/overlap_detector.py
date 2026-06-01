from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.ai.chunker import chunk_text

OVERLAP_THRESHOLD = 0.55


def detect_overlaps(students: dict[str, dict]) -> list[dict]:
    """
    students: { name: { "source_file": str, "text": str } }
    """
    indexed: list[tuple[str, str, str, str]] = []
    for name, data in students.items():
        source = data.get("source_file", "unknown")
        for i, chunk in enumerate(chunk_text(data.get("text", ""))):
            indexed.append((name, source, f"{name}-chunk-{i}", chunk))

    if len(indexed) < 2:
        return []

    texts = [item[3] for item in indexed]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(texts)
    sim = cosine_similarity(matrix)

    overlaps: list[dict] = []
    for i in range(len(indexed)):
        for j in range(i + 1, len(indexed)):
            score = float(sim[i, j])
            if score < OVERLAP_THRESHOLD:
                continue
            name_a, file_a, _, chunk_a = indexed[i]
            name_b, file_b, _, chunk_b = indexed[j]
            if name_a == name_b:
                continue
            excerpt = chunk_a if len(chunk_a) <= len(chunk_b) else chunk_b
            if len(excerpt) > 200:
                excerpt = excerpt[:197] + "..."
            overlaps.append(
                {
                    "student_a": name_a,
                    "student_b": name_b,
                    "file_a": file_a,
                    "file_b": file_b,
                    "similarity": round(score, 4),
                    "similarity_percent": round(score * 100, 1),
                    "excerpt": excerpt,
                }
            )

    overlaps.sort(key=lambda x: x["similarity"], reverse=True)
    return overlaps[:10]
