
from fastapi.testclient import TestClient

from app.main import app
from app.api import chat as chat_api


client = TestClient(app)

def enable_legacy_chat_for_test(monkeypatch):
    """Enable the legacy local-development endpoint for these tests."""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("AUTH_REQUIRED", "false")


def test_chat_returns_answer_and_sources(monkeypatch, tmp_path):
    """A valid question returns a generated answer and source references."""

    enable_legacy_chat_for_test(monkeypatch)

    fake_chunks = [
        {
            "content": "def calculate_total(price, quantity):\n    return price * quantity",
            "file_path": "main.py",
            "start_line": 1,
            "end_line": 2,
            "node_type": "function_definition",
        }
    ]

    monkeypatch.setattr(
        chat_api,
        "hybrid_search",
        lambda **kwargs: fake_chunks,
    )
    monkeypatch.setattr(
        chat_api,
        "generate_answer",
        lambda **kwargs: "The total is price multiplied by quantity.",
    )

    response = client.post(
        "/api/chat",
        json={
            "repository_path": str(tmp_path),
            "question": "How is the total calculated?",
            "top_k": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "How is the total calculated?"
    assert data["answer"] == "The total is price multiplied by quantity."
    assert data["sources"][0]["file_path"] == "main.py"
    assert data["sources"][0]["start_line"] == 1


def test_chat_rejects_empty_question(tmp_path):
    """Pydantic rejects an empty question before the endpoint runs."""
    
    response = client.post(
        "/api/chat",
        json={
            "repository_path": str(tmp_path),
            "question": "",
            "top_k": 5,
        },
    )

    assert response.status_code == 422


def test_chat_rejects_invalid_repository_path(monkeypatch,tmp_path):
    """A path that does not exist returns 404."""

    enable_legacy_chat_for_test(monkeypatch)

    missing_path = tmp_path / "does_not_exist"

    response = client.post(
        "/api/chat",
        json={
            "repository_path": str(missing_path),
            "question": "Explain the code",
            "top_k": 5,
        },
    )

    assert response.status_code == 404


def test_chat_returns_safe_message_when_no_chunks_found(
    monkeypatch, tmp_path
):
    """No retrieved chunks means Gemini is not called."""

    enable_legacy_chat_for_test(monkeypatch)

    monkeypatch.setattr(
        chat_api,
        "hybrid_search",
        lambda **kwargs: [],
    )

    def fail_if_called(**kwargs):
        raise AssertionError("Gemini should not be called without chunks.")

    monkeypatch.setattr(chat_api, "generate_answer", fail_if_called)

    response = client.post(
        "/api/chat",
        json={
            "repository_path": str(tmp_path),
            "question": "Explain an unknown function",
            "top_k": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sources"] == []
    assert "couldn't find relevant indexed code" in data["answer"]
