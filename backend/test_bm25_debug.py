
from rank_bm25 import BM25Okapi
from app.services.hybrid_search import _get_repository_chunks, _tokenize

repository_path = r"D:\CodebaseTestRepo"
query = "apply_discount"

corpus = _get_repository_chunks(repository_path)
tokenized_corpus = [_tokenize(chunk["content"]) for chunk in corpus]
query_tokens = _tokenize(query)

print("Number of chunks:", len(corpus))
print("Query tokens:", query_tokens)

for i, chunk in enumerate(corpus):
    print(f"\nChunk {i + 1}: {chunk['file_path']}")
    print("Lines:", chunk["start_line"], "-", chunk["end_line"])
    print("Content:", repr(chunk["content"]))
    print("Tokens:", tokenized_corpus[i])

if tokenized_corpus and query_tokens:
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)

    print("\nBM25 scores:")
    for i, score in enumerate(scores):
        print(f"Chunk {i + 1}: {float(score)}")
