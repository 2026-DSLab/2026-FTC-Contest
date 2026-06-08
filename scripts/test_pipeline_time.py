import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

import asyncio
import time

async def main():
    total_start = time.time()

    # 초기화
    t = time.time()
    from rag.pipeline import RAGPipeline
    pipeline = RAGPipeline(
        db_path="data/processed/chroma_db",
        excel_path="data/raw/scenarios.xlsx"
    )
    print(f"[초기화] {time.time()-t:.2f}s")

    query = "납품업자에게 사전 서면 약정 없이 판촉비를 부담시키고 있습니다."
    situation_type = "in_progress"

    # 1. Query Processor
    t = time.time()
    from rag.query.query_processor import process_query
    processed = await process_query(query)
    rewritten_query = processed["rewritten_query"]
    print(f"[1] Query Processor: {time.time()-t:.2f}s → {rewritten_query}")

    # 2. Hybrid Search
    t = time.time()
    hybrid_results = pipeline.hybrid_search.search(query=rewritten_query, top_k=10)
    print(f"[2] Hybrid Search: {time.time()-t:.2f}s → {len(hybrid_results)}개")

    # 여기 추가
    for i, doc in enumerate(hybrid_results):
        print(f"  [{i+1}] 청크 길이: {len(doc['content'])}자")

    # 3. Reranker
    t = time.time()
    reranked = pipeline.reranker.rerank(query=rewritten_query, docs=hybrid_results, top_k=10)
    print(f"[3] Reranker: {time.time()-t:.2f}s → {len(reranked)}개")

    # 4. LLM Filter
    t = time.time()
    from rag.retrieval.filter import llm_filter
    filtered = await llm_filter(query=rewritten_query, docs=reranked, top_k=5)
    print(f"[4] LLM Filter: {time.time()-t:.2f}s → {len(filtered)}개")

    # 5. Scenario Search
    t = time.time()
    scenario_results = pipeline.scenario_db.search(query=rewritten_query, situation_type=situation_type, top_k=3)
    print(f"[5] Scenario Search: {time.time()-t:.2f}s → {len(scenario_results)}개")

    print(f"\n[전체] {time.time()-total_start:.2f}s (초기화 제외)")

asyncio.get_event_loop().run_until_complete(main())