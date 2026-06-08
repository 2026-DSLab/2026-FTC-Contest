from rag.db.scenario_db import ScenarioDB
from rag.query.query_processor import process_query
from rag.retrieval.hybrid_search import HybridSearch
from rag.retrieval.reranker import Reranker
from rag.retrieval.filter import llm_filter
from schemas.rag_output import (
    RAGOutput, ResolutionDoc, ScenarioDoc,
    HybridSearchDoc, RerankedDoc, FilteredDoc,
)


class RAGPipeline:
    def __init__(
        self,
        db_path: str = "data/processed/chroma_db",
        excel_path: str = "data/raw/scenarios.xlsx"
    ):
        print("RAG 파이프라인 초기화 중...")
        print("ScenarioDB 초기화 중...")
        self.scenario_db = ScenarioDB(excel_path=excel_path)
        print("HybridSearch 초기화 중...")
        self.hybrid_search = HybridSearch(db_path=db_path)
        print("Reranker 초기화 중...")
        self.reranker = Reranker()
        print("RAG 파이프라인 초기화 완료")

    async def run(self, user_query: str, situation_type: str) -> RAGOutput:
        print("1. Query Processing 중...")
        processed = await process_query(user_query)
        rewritten_query = processed["rewritten_query"]
        query_intent = processed.get("intent")
        mcp_law_query = processed.get("mcp_law_query")
        mcp_prec_query = processed.get("mcp_prec_query")

        print("2. 의결서 Hybrid Search 중...")
        hybrid_results = self.hybrid_search.search(
            query=rewritten_query,
            top_k=10
        )

        print("3. Reranking 중...")
        reranked = await self.reranker.rerank_async(
            query=rewritten_query,
            docs=hybrid_results,
            top_k=10
        )

        print("4. LLM Filter 중...")
        filtered = await llm_filter(
            query=rewritten_query,
            docs=reranked,
            top_k=5
        )

        print("5. 엑셀 QA 검색 중...")
        scenario_results = self.scenario_db.search(
            query=rewritten_query,
            situation_type=situation_type,
            top_k=3
        )

        print("6. RAGOutput 구성 중...")
        resolution_docs = [
            ResolutionDoc(
                doc_id=doc["chunk_id"],
                content=doc["content"],
                score=doc["rerank_score"],
                metadata=doc["metadata"]
            )
            for doc in filtered
        ]

        scenario_docs = [
            ScenarioDoc(
                question=doc["question"],
                answer=doc["answer"],
                legal_interpretation=doc["legal_interpretation"],
                evidence=doc["evidence"],
                situation_type=doc["situation_type"]
            )
            for doc in scenario_results
        ]

        # 중간 과정 추적 데이터 구성
        hybrid_search_raw = [
            HybridSearchDoc(
                chunk_id=doc["chunk_id"],
                content=doc["content"],
                metadata=doc["metadata"],
                dense_rank=doc.get("dense_rank"),
                bm25_rank=doc.get("bm25_rank"),
                rrf_score=doc.get("score", 0.0),
            )
            for doc in hybrid_results
        ]

        reranked_raw = [
            RerankedDoc(
                chunk_id=doc["chunk_id"],
                content=doc["content"],
                metadata=doc["metadata"],
                rerank_score=doc.get("rerank_score", 0.0),
            )
            for doc in reranked
        ]

        filtered_raw = [
            FilteredDoc(
                chunk_id=doc["chunk_id"],
                content=doc["content"],
                metadata=doc["metadata"],
                rerank_score=doc.get("rerank_score", 0.0),
            )
            for doc in filtered
        ]

        return RAGOutput(
            user_query=user_query,
            situation_type=situation_type,
            rewritten_query=rewritten_query,
            query_intent=query_intent,
            mcp_law_query=mcp_law_query,
            mcp_prec_query=mcp_prec_query,
            resolution_docs=resolution_docs,
            scenario_docs=scenario_docs,
            hybrid_search_raw=hybrid_search_raw,
            reranked_raw=reranked_raw,
            filtered_raw=filtered_raw,
        )