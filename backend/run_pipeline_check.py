
from pathlib import Path

from app.services.repository_service import ingest_repository
from app.services.vector_store import search_code


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REPOSITORY = PROJECT_ROOT / "data" / "sample_repo"


if __name__ == "__main__":
    result = ingest_repository(str(SAMPLE_REPOSITORY))
    print("\nINDEX RESULT")
    print(result)

    matches = search_code(
        query="Which function multiplies two numbers?",
        repository_path=str(SAMPLE_REPOSITORY),
        top_k=3,
    )

    print("\nSEARCH RESULTS")

    for match in matches:
        print(f"\nFile: {match['file_path']}")
        print(
            f"Lines: {match['start_line']}-"
            f"{match['end_line']}"
        )
        print(f"Type: {match['node_type']}")
        print(f"Cosine distance: {match['distance']:.4f}")
        print(match["content"])
