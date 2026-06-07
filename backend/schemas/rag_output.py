from pydantic import BaseModel
from typing import List, Optional


class ResolutionDoc(BaseModel):
    doc_id: str
    content: str
    score: float
    metadata: dict


class ScenarioDoc(BaseModel):
    question: str
    answer: str
    legal_interpretation: str
    evidence: str
    situation_type: str


class HybridSearchDoc(BaseModel):
    """하이브리드 검색 단계별 중간 결과 (리랭킹 전)"""
    chunk_id: str
    content: str
    metadata: dict
    dense_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    rrf_score: float


class RerankedDoc(BaseModel):
    """리랭킹 후 결과 (LLM 필터 전)"""
    chunk_id: str
    content: str
    metadata: dict
    rerank_score: float


class FilteredDoc(BaseModel):
    """LLM 관련도 필터 통과 후 최종 청크"""
    chunk_id: str
    content: str
    metadata: dict
    rerank_score: float


class RAGOutput(BaseModel):
    user_query: str
    situation_type: str
    rewritten_query: str
    query_intent: Optional[str] = None     # "제재중심" | "법령중심" | "유사사례" | "시장영향"
    mcp_law_query: Optional[str] = None   # MCP 법령명 검색용 쿼리
    mcp_prec_query: Optional[str] = None  # MCP 판례 본문 검색용 쿼리
    resolution_docs: List[ResolutionDoc]
    scenario_docs: List[ScenarioDoc]
    # 중간 과정 추적용 필드 (4.3절 데이터 활용결과 문서화)
    hybrid_search_raw: List[HybridSearchDoc] = []
    reranked_raw: List[RerankedDoc] = []
    filtered_raw: List[FilteredDoc] = []