import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from rag.retrieval.hybrid_search import HybridSearch

search = HybridSearch(db_path="data/processed/chroma_db")

results = search.search(
    query="자사상품 검색 상단 노출 공정거래법 위반 여부",
    top_k=5
)

for i, r in enumerate(results):
    print(f"\n[{i+1}]")
    print(f"ID: {r['chunk_id']}")
    print(f"내용: {r['content'][:80]}...")
    print(f"의결서: {r['metadata']['의결서제목'][:40]}...")
    print(f"위반유형: {r['metadata']['위반유형']}")
    print(f"RRF 스코어: {r['score']:.6f}")