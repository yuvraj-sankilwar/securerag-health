"""Prompt builder for the RAG LLM pipeline."""

from app.rag.schemas import ChunkResult


def build_prompt(query: str, chunks: list[ChunkResult], role_name: str, user_name: str) -> list[dict]:
    """
    Build the messages list for the Anthropic Claude API.

    Constructs a system prompt that constrains the LLM to only use provided context,
    and a user message that includes the retrieved chunks and the original query.

    Args:
        query: The user's natural language query
        chunks: List of retrieved document chunks
        role_name: The user's role (e.g., "PHYSICIAN")
        user_name: The user's display name

    Returns:
        List of message dicts compatible with the Anthropic API:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    # System message — constraining the LLM behavior
    system_content = (
        f"You are a secure hospital information assistant. You serve {role_name} staff members.\n"
        f"Answer ONLY based on the retrieved document context provided below.\n"
        f"Do NOT use any knowledge outside the provided context.\n"
        f"If the context does not contain sufficient information to answer the query, "
        f"respond: 'I could not find relevant information in the authorized documents.'\n"
        f"Never reveal document IDs, chunk IDs, or internal metadata in your response.\n"
        f"Always maintain patient confidentiality. Do not speculate beyond the evidence."
    )

    # User message — context + query
    context_parts = []
    for chunk in chunks:
        context_parts.append(
            f"[Document: {chunk.title or 'Untitled'} | Type: {chunk.doc_type or 'Unknown'} | "
            f"Relevance: {chunk.score:.2f}]\n"
            f"{chunk.text}\n"
            f"---"
        )

    context_block = "\n".join(context_parts)

    user_content = f"Retrieved Document Context:\n\n{context_block}\n\nQuery: {query}"

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]
