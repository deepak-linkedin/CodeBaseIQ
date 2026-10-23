
import httpx

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
)


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_answer(
    question: str,
    context_chunks: list[dict],
) -> str:
    """Generate an answer grounded in retrieved source-code chunks."""

    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    if not context_chunks:
        return (
            "I couldn't find relevant code in the indexed repository "
            "to answer this question."
        )

    if LLM_PROVIDER.lower() != "gemini":
        raise RuntimeError(
            "Gemini is not enabled. Set LLM_PROVIDER=gemini in your .env file."
        )

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Configure it in the project .env file."
        )

    source_context = []

    for index, chunk in enumerate(context_chunks, start=1):
        source_context.append(
            f"""
Source {index}
File: {chunk.get("file_path", "Unknown")}
Lines: {chunk.get("start_line", "?")}-{chunk.get("end_line", "?")}
Code:
{chunk.get("content", "")}
"""
        )

    prompt = f"""
You are CodeBase Intelligence, an assistant that explains source code.

Answer the user's question using the supplied repository context.

Rules:
1. Ground factual claims in the supplied code.
2. Do not invent functions, files, or implementation details.
3. If the context is insufficient, clearly say so.
4. Reference relevant file paths and line numbers.
5. Explain the code clearly and directly.

Repository context:
{"".join(source_context)}

User question:
{question}
"""

    url = (
        f"{GEMINI_API_BASE_URL}/{GEMINI_MODEL}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
        },
    }

    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Gemini API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text[:1000]}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to the Gemini API: {exc}"
        ) from exc

    candidates = data.get("candidates", [])

    if not candidates:
        feedback = data.get("promptFeedback", {})
        raise RuntimeError(
            f"Gemini returned no answer. API feedback: {feedback}"
        )

    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "\n".join(
        part["text"]
        for part in parts
        if isinstance(part.get("text"), str)
    ).strip()

    if not answer:
        raise RuntimeError("Gemini returned an empty answer.")

    return answer
