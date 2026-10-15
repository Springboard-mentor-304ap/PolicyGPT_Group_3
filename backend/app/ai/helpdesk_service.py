from sqlalchemy.orm import Session

from backend.app.ai.llm_client import LLMClient
from backend.app.ai.quota import FEATURE_HELPDESK, consume_llm_quota
from backend.app.ai.retrieval_service import retrieve_relevant_chunks

SYSTEM_PROMPT = """
You are the AI Helpdesk for PolicyGPT, a government policy and scheme information platform.

Answer the user's questions ONLY using the provided knowledge base context.

Rules:
1. Do not use outside knowledge.
2. Do not invent or assume government policies, schemes, benefits, eligibility requirements, deadlines, documents, or application procedures.
3. If the provided context does not contain enough information to answer, clearly say that the available PolicyGPT knowledge base does not contain enough information.
4. Do not claim that a user is eligible for a scheme. Eligibility must be determined by PolicyGPT's eligibility checker.
5. When discussing a policy or scheme, distinguish clearly between the information provided in the context and anything the user is asking.
6. Be concise, clear, and helpful.
7. If multiple sources are relevant, synthesize them without adding facts that are not present in the context.
8. Do not combine separate policies or schemes into one program unless the context explicitly establishes that relationship.

Knowledge base context:
"""

def answer_helpdesk_question(
    db: Session,
    question: str,
    user_id=None,
    *,
    top_k: int = 5,
    min_similarity: float = 0.35,
) -> dict:
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    retrieved_chunks = retrieve_relevant_chunks(
        db,
        question,
        top_k=top_k,
        min_similarity=min_similarity,
    )

    if not retrieved_chunks:
        return {
            "answer": (
                "I couldn't find enough information in the PolicyGPT "
                "knowledge base to answer that question."
            ),
            "sources": [],
        }

    context_parts = []

    for index, (chunk, similarity) in enumerate(retrieved_chunks, 1):
        context_parts.append(
            f"""
SOURCE {index}
Type: {chunk.source_type}
Title: {chunk.title}
{chunk.content}
""".strip()
        )

    context = "\n\n---\n\n".join(context_parts)

    user_prompt = f"""
        Knowledge base context:

        {context}

        User question:
        {question}""".strip()

    # Metered right before the LLM call: retrieval-only answers (no chunks
    # found) above never reach the LLM and therefore cost no quota.
    if user_id is not None:
        consume_llm_quota(
            db,
            user_id=user_id,
            feature=FEATURE_HELPDESK,
        )

    client = LLMClient()

    answer = client.generate_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    sources = [
        {
            "id": str(chunk.id),
            "source_type": chunk.source_type,
            "title": chunk.title,
            "similarity": round(similarity, 4),
        }
        for chunk, similarity in retrieved_chunks
    ]

    return {
        "answer": answer,
        "sources": sources,
    }
