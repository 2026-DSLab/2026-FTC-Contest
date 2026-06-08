from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SituationType(str, Enum):
    SUSPECTED = "위반 의심 사항"
    IN_PROGRESS = "거래 진행 중"
    CONTRACT_BEFORE = "계약 체결 전"
    REGULAR_CHECK = "정기 점검"

    def to_rag_key(self) -> str:
        """RAG ScenarioDB가 기대하는 영문 키로 변환"""
        return {
            "위반 의심 사항": "suspected",
            "거래 진행 중": "in_progress",
            "계약 체결 전": "contract_before",
            "정기 점검": "regular_check",
        }[self.value]


class ScenarioDoc(BaseModel):
    """RAG ScenarioDB에서 반환하는 QA 문서"""
    question: str
    answer: str
    legal_interpretation: str
    evidence: str
    situation_type: str


class LawDocument(BaseModel):
    doc_type: str  # "law" | "precedent" | "ftc_decision" | "resolution_chunk"
    title: str
    content: str
    source_id: Optional[str] = None
    score: Optional[float] = None


class ExternalEvidence(BaseModel):
    laws: List[LawDocument] = Field(default_factory=list)
    precedents: List[LawDocument] = Field(default_factory=list)
    ftc_decisions: List[LawDocument] = Field(default_factory=list)
    resolution_chunks: List[LawDocument] = Field(default_factory=list)
    scenario_docs: List[ScenarioDoc] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            not self.laws
            and not self.precedents
            and not self.ftc_decisions
            and not self.resolution_chunks
            and not self.scenario_docs
        )


class AgentReport(BaseModel):
    agent_type: str  # "law" | "resolution" | "precedent" | "case"
    agent_name: str
    analysis: str
    confidence_score: int = Field(ge=0, le=100)
    key_findings: List[str]
    source_description: Optional[str] = None  # 에이전트 패널 하단 소스 텍스트 (2줄)
    limitations: Optional[str] = None


# ── 프론트엔드 출력용 구조화 모델 ──────────────────────────

class ChecklistItem(BaseModel):
    """컴플라이언스 체크리스트 항목"""
    emoji: str           # "🔴" | "🟡"
    title: str
    priority: str        # "high" | "medium"
    priority_label: str  # "필수" | "권장"
    description: str


class LegalBasisItem(BaseModel):
    """관련 법령 및 의결서 근거 항목"""
    title: str
    tag_type: str        # "info" | "warn" | "law" | "danger"
    tag_label: str       # 예: "핵심 선례", "판례", "법령"
    quote: str
    cite: str
    page_refs: List[str] = Field(default_factory=list)


class SimilarCaseTag(BaseModel):
    type: str   # "danger" | "info" | "warn" | "law"
    label: str


class SimilarCaseItem(BaseModel):
    """유사 사례 항목"""
    title: str
    description: str
    tags: List[SimilarCaseTag] = Field(default_factory=list)
    similarity: int  # 0-100


class ScenarioItem(BaseModel):
    """개별 시나리오"""
    context: str
    content: str


class ScenariosOutput(BaseModel):
    """기본 + 추가 시나리오"""
    basic: ScenarioItem
    extra: ScenarioItem


class FinalReport(BaseModel):
    original_query: str
    rewritten_query: str
    situation_type: str
    agent_reports: List[AgentReport]
    synthesis: str
    overall_confidence: int = Field(ge=0, le=100)
    risk_level: str  # "낮음" | "보통" | "높음" | "매우 높음"
    recommendations: List[str]
    caveats: Optional[str] = None
    # ── 프론트엔드 HTML 렌더링용 구조화 필드 ──────────────
    risk_score: Optional[int] = Field(default=None, ge=0, le=100)
    risk_weather: Optional[str] = None   # ☀️ | ⛅ | 🌧️ | ⛈️
    summary: Optional[str] = None        # 리스크 점수 아래 본문 첫 단락
    legal_basis: Optional[List[LegalBasisItem]] = None
    similar_cases: Optional[List[SimilarCaseItem]] = None
    legal_interpretation: Optional[str] = None
    checklist: Optional[List[ChecklistItem]] = None
    scenarios: Optional[ScenariosOutput] = None
