def to_suggestion_strength(similarity: float) -> int:
    """Map cosine/TF-IDF similarity (0-1) to 0-100 suggestion strength (not a grade)."""
    return max(0, min(100, round(similarity * 100)))
