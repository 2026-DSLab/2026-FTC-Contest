from __future__ import annotations

from enum import Enum
from typing import Optional

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
    laws: list[LawDocument] = Field(default_factory=list)
    precedents: list[LawDocument] = Field(default_factory=list)
    ftc_decisions: list[LawDocument] = Field(default_factory=list)
    resolution_chunks: list[LawDocument] = Field(default_factory=list)
    scenario_docs: list[ScenarioDoc] = Field(default_factory=list)

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
    key_findings: list[str]
    limitations: Optional[str] = None


class FinalReport(BaseModel):
    original_query: str
    rewritten_query: str
    situation_type: str
    agent_reports: list[AgentReport]
    synthesis: str
    overall_confidence: int = Field(ge=0, le=100)
    risk_level: str  # "낮음" | "보통" | "높음" | "매우 높음"
    recommendations: list[str]
    caveats: Optional[str] = None
