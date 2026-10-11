from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai.embedding_service import generate_embedding
from backend.app.models.knowledge_chunk import KnowledgeChunk


def retrieve_relevant_chunks(
        db: Session,
        query: str,
        *,
        top_k: int = 5,
        min_similarity: 0.35,
        relative_similarity: float = 0.85,
) -> list[tuple[KnowledgeChunk, float]]:
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    query_embedding = generate_embedding(query)

    distance = KnowledgeChunk.embedding.cosine_distance(
        query_embedding
    )

    similarity = 1-distance

    statement = (
        select(KnowledgeChunk, similarity.label("similarity"))
        .where(similarity >= min_similarity)
        .order_by(distance)
        .limit(top_k)
    )

    results = db.execute(statement).all()

    if not results:
        return []

    best_similarity = float(results[0][1])
    cutoff = max(
        min_similarity,
        best_similarity * relative_similarity,
    )

    return [
        (chunk, float(score))
        for chunk, score in results
        if float(score) >= cutoff
    ]