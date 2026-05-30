from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    UNFAIR_TRADE = "불공정거래행위"
    MARKET_DOMINANT = "시장지배적지위남용"
    MERGER = "기업결합"
    CARTEL = "부당공동행위"
    CONSUMER_PROTECTION = "소비자보호"
    CONTRACT = "계약거래일반"
    OTHER = "기타"


class QueryIntent(BaseModel):
    category: IntentCategory
    sub_intent: str
    legal_issues: list[str]


class RewrittenQuery(BaseModel):
    original: str
    rewritten: str
    intent: QueryIntent
    search_keywords: list[str]


class LawDocument(BaseModel):
    doc_type: str  # "law" | "precedent" | "ftc_decision"
    title: str
    content: str
    source_id: Optional[str] = None


class ExternalEvidence(BaseModel):
    laws: list[LawDocument] = Field(default_factory=list)
    precedents: list[LawDocument] = Field(default_factory=list)
    ftc_decisions: list[LawDocument] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.laws and not self.precedents and not self.ftc_decisions


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
    intent_category: str
    legal_issues: list[str]
    agent_reports: list[AgentReport]
    synthesis: str
    overall_confidence: int = Field(ge=0, le=100)
    risk_level: str  # "낮음" | "보통" | "높음" | "매우 높음"
    recommendations: list[str]
    caveats: Optional[str] = None
