import math
import re
from collections import Counter
from dataclasses import dataclass

from app.ai.rubric_criteria import Criterion

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """
    a an the this that these those of in on at to for from by with as is are was
    were be been being it its and or not no but if then so we our you your they
    their he she his her i me my them us do does did has have had will would can
    could should may might must about into over under than too very can't out
    de het een en van te in op aan met voor door dat die deze dit is zijn was
    waren wordt worden niet wel maar als dan ook om naar bij uit over onder ik je
    jij wij hij zij ze hun hen ons onze dit daar er nog meer zeer
    """.split()
)


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall((text or "").lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


@dataclass(frozen=True)
class EvidenceChunk:
    evidence_id: str
    chunk_index: int
    text: str


@dataclass(frozen=True)
class ChunkMatch:
    chunk: EvidenceChunk
    score: float


@dataclass(frozen=True)
class CriterionResult:
    criterion: Criterion
    matches: list[ChunkMatch]


class _TfidfIndex:
    def __init__(self, documents: list[list[str]]):
        self._n = len(documents)
        document_frequency: Counter[str] = Counter()
        for tokens in documents:
            document_frequency.update(set(tokens))
        self._idf = {
            term: math.log((self._n + 1) / (freq + 1)) + 1.0
            for term, freq in document_frequency.items()
        }
        self._doc_vectors = [self._vectorize(tokens) for tokens in documents]

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        term_freq = Counter(tokens)
        total = len(tokens)
        vector: dict[str, float] = {}
        for term, count in term_freq.items():
            idf = self._idf.get(term)
            if idf is None:
                continue
            vector[term] = (count / total) * idf
        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        if norm == 0.0:
            return {}
        return {term: weight / norm for term, weight in vector.items()}

    def similarities(self, query_tokens: list[str]) -> list[float]:
        query = self._vectorize(query_tokens)
        if not query:
            return [0.0] * self._n
        scores: list[float] = []
        for doc in self._doc_vectors:
            small, large = (query, doc) if len(query) <= len(doc) else (doc, query)
            scores.append(sum(weight * large.get(term, 0.0) for term, weight in small.items()))
        return scores


def match_criteria(
    criteria: list[Criterion],
    chunks: list[EvidenceChunk],
    *,
    threshold: float,
    top_k: int,
) -> list[CriterionResult]:
    if not chunks:
        return [CriterionResult(criterion=c, matches=[]) for c in criteria]

    index = _TfidfIndex([_tokenize(chunk.text) for chunk in chunks])

    results: list[CriterionResult] = []
    for criterion in criteria:
        scores = index.similarities(_tokenize(criterion.text))
        ranked = sorted(
            (
                ChunkMatch(chunk=chunk, score=score)
                for chunk, score in zip(chunks, scores)
                if score >= threshold
            ),
            key=lambda match: match.score,
            reverse=True,
        )
        results.append(CriterionResult(criterion=criterion, matches=ranked[:top_k]))
    return results
