
from pathlib import Path

from app.services.vector_store import search_code
from app.services.hybrid_search import hybrid_search


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REPOSITORY = PROJECT_ROOT / "data" / "sample_repo"

QUESTIONS = [
    "Which function multiplies two numbers?",
    "Find calculate_total",
    "Where is Calculator defined?",
    "Find the add method",
    "How does this code calculate the total?",
]


def print_results(label: str, results: list[dict]) -> None:
    print(f"\n{label}")

    if not results:
        print("No results found.")
        return

    for rank, result in enumerate(results, start=1):
        print(
            f"\n{rank}. {result.get('file_path')} "
            f"(lines {result.get('start_line')}-"
            f"{result.get('end_line')})"
        )
        print(f"   Type: {result.get('node_type')}")

        if "rrf_score" in result:
            print(f"   RRF score: {result['rrf_score']:.6f}")

        if "distance" in result:
            print(f"   Semantic distance: {result['distance']}")

        if result.get("semantic_distance") is not None:
            print(
                f"   Semantic distance: "
                f"{result['semantic_distance']}"
            )

        if result.get("bm25_score") is not None:
            print(f"   BM25 score: {result['bm25_score']:.4f}")

        print(f"   Code:\n{result.get('content', '')}")


def main() -> None:
    repository_path = str(SAMPLE_REPOSITORY.resolve())

    for question in QUESTIONS:
        print("\n" + "=" * 80)
        print(f"QUESTION: {question}")

        semantic_results = search_code(
            query=question,
            repository_path=repository_path,
            top_k=5,
        )

        hybrid_results = hybrid_search(
            query=question,
            repository_path=repository_path,
            top_k=5,
        )

        print_results("SEMANTIC-ONLY RESULTS", semantic_results)
        print_results("HYBRID RESULTS", hybrid_results)


if __name__ == "__main__":
    main()
