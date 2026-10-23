
from app.services.hybrid_search import hybrid_search

repository_path = r"D:\CodebaseTestRepo"

queries = [
    "How is the total price calculated?",
    "apply_discount",
    "quantity multiplied by price",
]

for query in queries:
    print(f"\n{'=' * 60}")
    print(f"Query: {query}")
    print("=" * 60)

    results = hybrid_search(
        query=query,
        repository_path=repository_path,
        top_k=5,
    )

    print(f"Results found: {len(results)}")

    for index, result in enumerate(results, start=1):
        print(f"\n--- Result {index} ---")
        for key, value in result.items():
            print(f"{key}: {value}")
