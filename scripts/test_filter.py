import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from rag.retrieval.hybrid_search import HybridSearch
from rag.retrieval.reranker import Reranker
from rag.retrieval.filter import llm_filter

query = "자사상품 검색 상단 노출 공정거래법 위반 여부"

async def main():
    # 1. Hybrid Search
    print("Hybrid Search 중...")
    search = HybridSearch(db_path="data/processed/chroma_db")
    hybrid_results = search.search(query=query, top_k=20)
    print(f"Hybrid 결과: {len(hybrid_results)}개")

    # 2. Reranking
    print("\nReranking 중...")
    reranker = Reranker()
    reranked = reranker.rerank(query=query, docs=hybrid_results, top_k=10)
    print(f"Reranking 결과: {len(reranked)}개")

    # 3. LLM Filter
    print("\nLLM Filter 중...")
    filtered = await llm_filter(query=query, docs=reranked, top_k=5)
    print(f"Filter 결과: {len(filtered)}개")

    print(f"\n[최종 결과 Top 5]")
    for i, r in enumerate(filtered):
        print(f"\n[{i+1}]")
        print(f"내용: {r['content'][:80]}...")
        print(f"의결서: {r['metadata']['의결서제목'][:40]}...")
        print(f"Rerank 스코어: {r['rerank_score']:.4f}")

asyncio.run(main())

# python scripts/test_filter.py