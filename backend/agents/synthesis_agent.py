"""
종합 분석 에이전트 (최종 단계)
4개 에이전트의 보고서와 Confidence Score를 종합하여 최종 레포트를 생성합니다.
"""
from __future__ import annotations

import json

from openai import OpenAI

from models import (
    AgentReport,
    ChecklistItem,
    FinalReport,
    LegalBasisItem,
    ScenarioItem,
    ScenariosOutput,
    SimilarCaseItem,
    SimilarCaseTag,
)

# ──────────────────────────────────────────────
# 프롬프트 수정 포인트 ▼
# ──────────────────────────────────────────────
_SYSTEM_PROMPT = """당신은 공정거래 법률 종합 분석 전문가입니다.

4개의 전문 에이전트(법령 해석, 의결서 해석, 판례 해석, 사례 기반 해석)의 분석 보고서를
Confidence Score를 가중치로 활용하여 통합하고 최종 법률 의견서를 작성하세요.

**종합 분석 방법**
1. 고신뢰 보고서 우선: Confidence Score가 높은 보고서의 결론에 더 큰 비중을 두세요.
2. 상충 의견 조율: 에이전트 간 결론이 다를 경우 그 이유를 명확히 설명하고 균형 있는 결론을 도출하세요.
3. 리스크 스코어 산정: 법적 위험 수준을 0~100 점수로 산정하세요 (0=위험 없음, 100=매우 위험).
4. 신뢰도 산정: 4개 에이전트 점수를 고려하여 전체 분석의 신뢰도를 0~100으로 산정하세요.
5. 구조화된 근거 작성: 관련 법령·의결서 근거를 항목별로 정리하고 핵심 인용문을 포함하세요.
6. 유사 사례 정리: 의결서·판례 자료에서 도출한 유사 사례를 유사도 점수와 함께 정리하세요.
7. 법리 해석 작성: 핵심 쟁점과 판단 기준을 설명하는 법리 해석을 작성하세요.
8. 체크리스트 작성: 사용자가 즉시 실행할 수 있는 컴플라이언스 체크리스트를 작성하세요.
   - 🔴 필수(high): 즉시 점검·조치가 필요한 사항 (3개 이상)
   - 🟡 권장(medium): 예방적으로 검토하면 좋은 사항 (2개 이상)
   각 항목은 구체적 제목과 2~3문장 설명을 포함해야 합니다.
9. 시나리오 작성: 기본 시나리오(직접적 위반 점검)와 추가 시나리오(복합 상황 점검)를 각각 작성하세요.

**주의사항**
- 이 분석은 법률 참고자료이며 공식 법률 자문을 대체하지 않습니다.
- 불확실한 부분은 명확히 표시하고 전문 변호사 상담을 권고하세요.
- 체크리스트 항목은 사용자가 실무에서 즉시 활용할 수 있도록 구체적으로 작성하세요."""
# ──────────────────────────────────────────────

_SYNTHESIS_TOOL = {
    "type": "function",
    "function": {
        "name": "output_final_report",
        "description": "최종 종합 법률 분석 보고서를 출력합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "synthesis": {
                    "type": "string",
                    "description": "4개 에이전트 보고서를 종합한 최종 분석 (마크다운 형식, 상세)",
                },
                "overall_confidence": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "전체 분석의 종합 신뢰도 점수 (분석 근거의 충분성)",
                },
                "risk_score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "법적 리스크 점수 (0=위험 없음, 100=매우 위험). 위반 가능성·제재 수준·선례 일치도를 종합하여 산정",
                },
                "risk_level": {
                    "type": "string",
                    "enum": ["낮음", "보통", "높음", "매우 높음"],
                    "description": "법적 위험 수준",
                },
                "summary": {
                    "type": "string",
                    "description": "분석 결과 요약 단락 (2~3문장, 핵심 리스크와 관련 법조문 언급)",
                },
                "legal_basis": {
                    "type": "array",
                    "description": "관련 법령 및 의결서 근거 목록 (2~4건)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "법령/의결서 제목"},
                            "tag_type": {
                                "type": "string",
                                "enum": ["info", "warn", "law", "danger"],
                                "description": "뱃지 색상 유형 (info=파랑, warn=주황, law=보라, danger=빨강)",
                            },
                            "tag_label": {"type": "string", "description": "뱃지 텍스트 (예: 핵심 선례, 판례, 법령)"},
                            "quote": {"type": "string", "description": "핵심 인용 문구"},
                            "cite": {"type": "string", "description": "출처 (기관·문서번호·날짜·과징금·유사도 등)"},
                            "page_refs": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "페이지 참조 목록 (예: ['p.1-2', 'p.93']). 없으면 빈 배열",
                            },
                        },
                        "required": ["title", "tag_type", "tag_label", "quote", "cite"],
                    },
                },
                "similar_cases": {
                    "type": "array",
                    "description": "유사 사례 목록 (2~4건)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "사건명 및 행위 요약"},
                            "description": {"type": "string", "description": "사건 상세 설명 (제재 결과 포함)"},
                            "tags": {
                                "type": "array",
                                "description": "사건 태그 목록 (제재 유형, 적용 법령 등)",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["danger", "info", "warn", "law"]},
                                        "label": {"type": "string"},
                                    },
                                    "required": ["type", "label"],
                                },
                            },
                            "similarity": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "유사도 점수",
                            },
                        },
                        "required": ["title", "description", "tags", "similarity"],
                    },
                },
                "legal_interpretation": {
                    "type": "string",
                    "description": "법리 해석 본문 (2~3단락, 핵심 쟁점과 판단 기준 설명)",
                },
                "checklist": {
                    "type": "array",
                    "description": "컴플라이언스 체크리스트 항목 (필수 3개 이상 + 권장 2개 이상)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "emoji": {
                                "type": "string",
                                "enum": ["🔴", "🟡"],
                                "description": "🔴=필수(즉시 조치), 🟡=권장(예방적 검토)",
                            },
                            "title": {"type": "string", "description": "점검 항목 제목 (간결하게)"},
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium"],
                                "description": "우선순위 코드",
                            },
                            "priority_label": {
                                "type": "string",
                                "enum": ["필수", "권장"],
                                "description": "우선순위 표시 텍스트",
                            },
                            "description": {
                                "type": "string",
                                "description": "점검 항목 상세 설명 (2~3문장, 구체적 행동 지침 포함)",
                            },
                        },
                        "required": ["emoji", "title", "priority", "priority_label", "description"],
                    },
                },
                "scenarios": {
                    "type": "object",
                    "description": "적용 시나리오 (기본·추가 2가지)",
                    "properties": {
                        "basic": {
                            "type": "object",
                            "description": "기본 시나리오 — 사용자 질문과 가장 직접적으로 연결된 상황",
                            "properties": {
                                "context": {"type": "string", "description": "상황 설정 (2~3문장)"},
                                "content": {"type": "string", "description": "이 시나리오의 핵심 점검 사항 및 판단 근거 (3~5문장)"},
                            },
                            "required": ["context", "content"],
                        },
                        "extra": {
                            "type": "object",
                            "description": "추가 시나리오 — 복합·혼합 운용 상황에 대한 점검",
                            "properties": {
                                "context": {"type": "string", "description": "상황 설정 (2~3문장)"},
                                "content": {"type": "string", "description": "이 시나리오의 핵심 점검 사항 및 판단 근거 (3~5문장)"},
                            },
                            "required": ["context", "content"],
                        },
                    },
                    "required": ["basic", "extra"],
                },
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "구체적 행동 권고사항 (3~6개)",
                },
                "caveats": {
                    "type": "string",
                    "description": "분석의 한계 및 면책 조항",
                },
            },
            "required": [
                "synthesis", "overall_confidence", "risk_score", "risk_level",
                "summary", "legal_basis", "similar_cases", "legal_interpretation",
                "checklist", "scenarios", "recommendations", "caveats",
            ],
        },
    },
}


def _score_to_weather(risk_score: int) -> str:
    if risk_score < 40:
        return "☀️"
    elif risk_score < 70:
        return "⛅"
    elif risk_score < 90:
        return "🌧️"
    return "⛈️"


def _format_agent_reports(reports: list[AgentReport]) -> str:
    parts = []
    for r in reports:
        bar = "█" * (r.confidence_score // 10) + "░" * (10 - r.confidence_score // 10)
        section = (
            f"## {r.agent_name} (신뢰도: {r.confidence_score}/100 [{bar}])\n\n"
            f"{r.analysis}\n\n"
            f"**핵심 발견:**\n" + "\n".join(f"- {f}" for f in r.key_findings)
        )
        if r.limitations:
            section += f"\n\n**한계:** {r.limitations}"
        parts.append(section)
    return "\n\n---\n\n".join(parts)


class SynthesisAgent:
    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def synthesize(
        self,
        original_query: str,
        rewritten_query: str,
        situation_type: str,
        agent_reports: list[AgentReport],
    ) -> FinalReport:
        reports_text = _format_agent_reports(agent_reports)
        user_message = (
            f"## 원본 질문\n{original_query}\n\n"
            f"## 재작성 질문\n{rewritten_query}\n\n"
            f"## 상황 유형\n{situation_type}\n\n"
            f"## 전문 에이전트 분석 보고서\n\n{reports_text}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=6000,
            tools=[_SYNTHESIS_TOOL],
            tool_choice={"type": "function", "function": {"name": "output_final_report"}},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        raw = response.choices[0].message.tool_calls[0].function.arguments
        data = json.loads(raw)

        avg_confidence = (
            sum(r.confidence_score for r in agent_reports) // len(agent_reports)
            if agent_reports else 50
        )

        risk_score = data.get("risk_score", avg_confidence)

        # legal_basis 파싱
        legal_basis = [
            LegalBasisItem(
                title=item["title"],
                tag_type=item["tag_type"],
                tag_label=item["tag_label"],
                quote=item["quote"],
                cite=item["cite"],
                page_refs=item.get("page_refs") or [],
            )
            for item in (data.get("legal_basis") or [])
        ]

        # similar_cases 파싱
        similar_cases = [
            SimilarCaseItem(
                title=item["title"],
                description=item["description"],
                tags=[SimilarCaseTag(type=t["type"], label=t["label"]) for t in (item.get("tags") or [])],
                similarity=item["similarity"],
            )
            for item in (data.get("similar_cases") or [])
        ]

        # checklist 파싱
        checklist = [
            ChecklistItem(
                emoji=item["emoji"],
                title=item["title"],
                priority=item["priority"],
                priority_label=item["priority_label"],
                description=item["description"],
            )
            for item in (data.get("checklist") or [])
        ]

        # scenarios 파싱
        scenarios_raw = data.get("scenarios")
        scenarios = None
        if scenarios_raw:
            scenarios = ScenariosOutput(
                basic=ScenarioItem(
                    context=scenarios_raw["basic"]["context"],
                    content=scenarios_raw["basic"]["content"],
                ),
                extra=ScenarioItem(
                    context=scenarios_raw["extra"]["context"],
                    content=scenarios_raw["extra"]["content"],
                ),
            )

        return FinalReport(
            original_query=original_query,
            rewritten_query=rewritten_query,
            situation_type=situation_type,
            agent_reports=agent_reports,
            synthesis=data.get("synthesis", ""),
            overall_confidence=data.get("overall_confidence", avg_confidence),
            risk_score=risk_score,
            risk_weather=_score_to_weather(risk_score),
            risk_level=data.get("risk_level", "보통"),
            summary=data.get("summary") or None,
            legal_basis=legal_basis or None,
            similar_cases=similar_cases or None,
            legal_interpretation=data.get("legal_interpretation") or None,
            checklist=checklist or None,
            scenarios=scenarios,
            recommendations=data.get("recommendations", []),
            caveats=data.get("caveats") or None,
        )
