
from app.services.hybrid_search import (
    _reciprocal_rank_fusion,
    _tokenize,
)


def test_tokenize_preserves_complete_identifier():
    tokens = _tokenize("Find calculate_total")

    assert "calculate_total" in tokens
    assert "calculate" in tokens
    assert "total" in tokens


def test_rrf_combines_semantic_and_keyword_rankings():
    semantic = [
        {
            "content": "def calculate_total(): pass",
            "file_path": "calculator.py",
            "start_line": 1,
            "end_line": 1,
            "node_type": "function_definition",
            "distance": 0.2,
        },
        {
            "content": "def add(): pass",
            "file_path": "calculator.py",
            "start_line": 3,
            "end_line": 3,
            "node_type": "function_definition",
            "distance": 0.3,
        },
    ]

    keyword = [
        {
            "content": "def add(): pass",
            "file_path": "calculator.py",
            "start_line": 3,
            "end_line": 3,
            "node_type": "function_definition",
            "bm25_score": 2.0,
        },
        {
            "content": "def calculate_total(): pass",
            "file_path": "calculator.py",
            "start_line": 1,
            "end_line": 1,
            "node_type": "function_definition",
            "bm25_score": 1.0,
        },
    ]

    results = _reciprocal_rank_fusion(semantic, keyword)

    assert len(results) == 2
    assert results[0]["rrf_score"] == results[1]["rrf_score"]
    assert results[0]["semantic_rank"] is not None
    assert results[0]["bm25_rank"] is not None


def test_rrf_deduplicates_identical_chunks():
    chunk = {
        "content": "def multiply(a, b): return a * b",
        "file_path": "calculator.py",
        "start_line": 1,
        "end_line": 1,
        "node_type": "function_definition",
    }

    results = _reciprocal_rank_fusion(
        semantic_results=[{**chunk, "distance": 0.1}],
        keyword_results=[{**chunk, "bm25_score": 2.0}],
    )

    assert len(results) == 1
    assert results[0]["semantic_rank"] == 1
    assert results[0]["bm25_rank"] == 1
    assert results[0]["rrf_score"] > 0


def test_rrf_keeps_source_metadata():
    chunk = {
        "content": "class Calculator: pass",
        "file_path": "calculator.py",
        "start_line": 1,
        "end_line": 1,
        "node_type": "class_definition",
    }

    results = _reciprocal_rank_fusion(
        semantic_results=[{**chunk, "distance": 0.1}],
        keyword_results=[],
    )

    assert results[0]["file_path"] == "calculator.py"
    assert results[0]["start_line"] == 1
    assert results[0]["end_line"] == 1
    assert results[0]["node_type"] == "class_definition"
