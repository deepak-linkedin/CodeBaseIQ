
from app.services.llm_service import generate_answer
from app.services.hybrid_search import hybrid_search


repository_path = r"D:\CodebaseTestRepo"

question = "How is the total price calculated?"

context_chunks = hybrid_search(
    query=question,
    repository_path=repository_path,
    top_k=5,
)

print("Retrieved chunks:", len(context_chunks))

answer = generate_answer(
    question=question,
    context_chunks=context_chunks,
)

print("\nAnswer:\n")
print(answer)
