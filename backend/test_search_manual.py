
from app.services.vector_store import search_code

repository_path = r"D:\CodebaseTestRepo"

results = search_code(
    query="How is the total price calculated?",
    repository_path=repository_path,
    top_k=5,
)

print(f"Results found: {len(results)}")

for index, result in enumerate(results, start=1):
    print(f"\n--- Result {index} ---")
    for key, value in result.items():
        print(f"{key}: {value}")
