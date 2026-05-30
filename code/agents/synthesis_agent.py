"""
종합 분석 에이전트 (Step 5)
4개 에이전트의 보고서와 Confidence Score를 종합하여 최종 레포트를 생성합니다.
"""
from __future__ import annotations

import json

from openai import OpenAI

from ..models import AgentReport, FinalReport, RewrittenQuery

# ──────────────────────────────────────────────
# 프롬프트 수정 포인트 ▼
# ──────────────────────────────────────────────
_SYSTEM_PROMPT = """당신은 공정거래 법률 종합 분석 전문가입니다.

4개의 전문 에이전트(법령 해석, 의결서 해석, 판례 해석, 사례 기반 해석)의 분석 보고서를
Confidence Score를 가중치로 활용하여 통합하고 최종 법률 의견서를 작성하세요.

**종합 분석 방법**
1. 고신뢰 보고서 우선: Confidence Score가 높은 보고서의 결론에 더 큰 비중을 두세요.
2. 상충 의견 조율: 에이전트 간 결론이 다를 경우 그 이유를 명확히 설명하고 균형 있는 결론을 도출하세요.
3. 종합 신뢰도 산정: 4개 에이전트의 점수를 고려하여 전체 분석의 신뢰도를 0~100으로 산정하세요.
4. 리스크 수준 판단: 법적 위험 수준을 "낮음/보통/높음/매우 높음"으로 평가하세요.
5. 실질적 권고사항: 의뢰인이 취할 수 있는 구체적 행동 방안을 제시하세요.

**주의사항**
- 이 분석은 법률 참고자료이며 공식 법률 자문을 대체하지 않습니다.
- 불확실한 부분은 명확히 표시하고 전문 변호사 상담을 권고하세요."""
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
                    "description": "전체 분석의 종합 신뢰도 점수",
                },
                "risk_level": {
                    "type": "string",
                    "enum": ["낮음", "보통", "높음", "매우 높음"],
                    "description": "법적 위험 수준",
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
            "required": ["synthesis", "overall_confidence", "risk_level", "recommendations", "caveats"],
        },
    },
}


def _format_agent_reports(reports: list[AgentReport]) -> str:
    parts = []
    for r in reports:
        score_bar = "█" * (r.confidence_score // 10) + "░" * (10 - r.confidence_score // 10)
        parts.append(
            f"## {r.agent_name} (신뢰도: {r.confidence_score}/100 [{score_bar}])\n\n"
            f"{r.analysis}\n\n"
            f"**핵심 발견:**\n" + "\n".join(f"- {f}" for f in r.key_findings)
            + (f"\n\n**한계:** {r.limitations}" if r.limitations else "")
        )
    return "\n\n---\n\n".join(parts)


class SynthesisAgent:
    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def synthesize(
        self,
        query: RewrittenQuery,
        agent_reports: list[AgentReport],
    ) -> FinalReport:
        reports_text = _format_agent_reports(agent_reports)
        user_message = (
            f"## 원본 질문\n{query.original}\n\n"
            f"## 재작성 질문\n{query.rewritten}\n\n"
            f"## 법률 쟁점\n" + "\n".join(f"- {i}" for i in query.intent.legal_issues) + "\n\n"
            f"## 전문 에이전트 분석 보고서\n\n{reports_text}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
            tools=[_SYNTHESIS_TOOL],
            tool_choice={"type": "function", "function": {"name": "output_final_report"}},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        data = json.loads(response.choices[0].message.tool_calls[0].function.arguments)

        return FinalReport(
            original_query=query.original,
            rewritten_query=query.rewritten,
            intent_category=query.intent.category.value,
            legal_issues=query.intent.legal_issues,
            agent_reports=agent_reports,
            synthesis=data["synthesis"],
            overall_confidence=data["overall_confidence"],
            risk_level=data["risk_level"],
            recommendations=data["recommendations"],
            caveats=data.get("caveats") or None,
        )
