"""에이전트 공통 기반 클래스"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod

from openai import OpenAI

from models import AgentReport, ExternalEvidence

REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "output_report",
        "description": "분석 결과를 구조화된 보고서 형식으로 출력합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "analysis": {
                    "type": "string",
                    "description": "상세 법률 분석 내용 (마크다운 형식)",
                },
                "confidence_score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "분석 신뢰도 점수 (0~100). 관련 증거가 충분하고 법리가 명확할수록 높음.",
                },
                "key_findings": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "핵심 발견 사항 목록 (3~5개)",
                },
                "limitations": {
                    "type": "string",
                    "description": "분석의 한계점 또는 불확실한 부분 (없으면 빈 문자열)",
                },
            },
            "required": ["analysis", "confidence_score", "key_findings", "limitations"],
        },
    },
}


def _format_evidence(evidence: ExternalEvidence) -> str:
    """ExternalEvidence 전체를 Claude에게 전달할 텍스트로 변환합니다."""
    parts = []

    if evidence.resolution_chunks:
        parts.append("## RAG 검색 의결서 청크")
        for doc in evidence.resolution_chunks:
            header = doc.title or "(제목 없음)"
            if doc.score is not None:
                header += f" (관련도: {doc.score:.3f})"
            parts.append(f"### {header}")
            parts.append(doc.content[:3000])

    if evidence.scenario_docs:
        parts.append("## 유사 시나리오 Q&A")
        for doc in evidence.scenario_docs:
            parts.append(f"**Q: {doc.question}**")
            parts.append(f"A: {doc.answer}")
            if doc.legal_interpretation:
                parts.append(f"법적 해석: {doc.legal_interpretation}")
            if doc.evidence:
                parts.append(f"근거: {doc.evidence}")

    if evidence.laws:
        parts.append("## MCP 검색 법령")
        for doc in evidence.laws:
            parts.append(f"### {doc.title or '(제목 없음)'}")
            parts.append(doc.content[:3000])

    if evidence.precedents:
        parts.append("## MCP 검색 판례")
        for doc in evidence.precedents:
            parts.append(f"### {doc.title or '(제목 없음)'}")
            parts.append(doc.content[:3000])

    if evidence.ftc_decisions:
        parts.append("## MCP 검색 공정위 결정문")
        for doc in evidence.ftc_decisions:
            parts.append(f"### {doc.title or '(제목 없음)'}")
            parts.append(doc.content[:3000])

    return "\n\n".join(parts) if parts else "검색된 외부 자료 없음"


class BaseAgent(ABC):
    agent_type: str = ""
    agent_name: str = ""

    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        ...

    def analyze(
        self,
        original_query: str,
        rewritten_query: str,
        evidence: ExternalEvidence,
    ) -> AgentReport:
        evidence_text = _format_evidence(evidence)
        user_message = (
            f"## 원본 질문\n{original_query}\n\n"
            f"## 분석 대상 질문 (재작성)\n{rewritten_query}\n\n"
            f"## 외부 자료\n{evidence_text}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=2048,
            tools=[REPORT_TOOL],
            tool_choice={"type": "function", "function": {"name": "output_report"}},
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        data = json.loads(response.choices[0].message.tool_calls[0].function.arguments)

        return AgentReport(
            agent_type=self.agent_type,
            agent_name=self.agent_name,
            analysis=data["analysis"],
            confidence_score=data["confidence_score"],
            key_findings=data["key_findings"],
            limitations=data.get("limitations") or None,
        )
