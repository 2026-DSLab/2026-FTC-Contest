"""
Step 1: Query Rewriting & Intent Classification
사용자 입력 쿼리를 법률 전문 쿼리로 재작성하고 의도를 분류합니다.
"""
from __future__ import annotations

import json

from openai import OpenAI

from .models import IntentCategory, QueryIntent, RewrittenQuery

# ──────────────────────────────────────────────
# 프롬프트 (수정 포인트 ▼)
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 공정거래 및 경쟁법 전문 법률 AI 어시스턴트입니다.
사용자의 질문을 분석하여 다음 두 가지 작업을 수행하세요.

1. **쿼리 재작성**: 사용자의 구어체 질문을 법률 데이터베이스 검색에 적합한 전문 법률 용어로 재작성합니다.
   - 핵심 법률 쟁점을 명확히 드러내세요.
   - 관련 법령명(공정거래법, 표시광고법 등)을 포함하세요.
   - 불필요한 감정적 표현은 제거하세요.

2. **의도 분류**: 질문의 법률적 의도를 분류합니다.
   카테고리:
   - 불공정거래행위: 거래상 지위 남용, 불공정한 거래 조건 등
   - 시장지배적지위남용: 독점, 시장 지배력 남용 행위
   - 기업결합: M&A, 합병, 지분 취득 등
   - 부당공동행위: 담합, 가격 고정, 시장 분할 등
   - 소비자보호: 소비자 피해, 표시광고 위반 등
   - 계약거래일반: 일반적인 계약 분쟁, 거래 관련 법률 문의
   - 기타: 위 카테고리에 해당하지 않는 경우"""

REWRITE_TOOL = {
    "type": "function",
    "function": {
        "name": "output_rewritten_query",
        "description": "재작성된 쿼리와 의도 분류 결과를 출력합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "rewritten": {
                    "type": "string",
                    "description": "법률 전문 용어로 재작성된 쿼리",
                },
                "category": {
                    "type": "string",
                    "enum": [c.value for c in IntentCategory],
                    "description": "질문 의도 카테고리",
                },
                "sub_intent": {
                    "type": "string",
                    "description": "카테고리 내 구체적인 법률 쟁점 (1~2문장)",
                },
                "legal_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "식별된 주요 법률 쟁점 목록 (3~5개)",
                },
                "search_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "법령DB 검색에 사용할 핵심 키워드 (3~7개)",
                },
            },
            "required": ["rewritten", "category", "sub_intent", "legal_issues", "search_keywords"],
        },
    },
}
# ──────────────────────────────────────────────


class QueryRewriter:
    def __init__(self, client: OpenAI, model: str = "gpt-4o-mini"):
        self.client = client
        self.model = model

    def rewrite(self, user_query: str) -> RewrittenQuery:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1024,
            tools=[REWRITE_TOOL],
            tool_choice={"type": "function", "function": {"name": "output_rewritten_query"}},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_query},
            ],
        )

        data = json.loads(response.choices[0].message.tool_calls[0].function.arguments)

        return RewrittenQuery(
            original=user_query,
            rewritten=data["rewritten"],
            intent=QueryIntent(
                category=IntentCategory(data["category"]),
                sub_intent=data["sub_intent"],
                legal_issues=data["legal_issues"],
            ),
            search_keywords=data["search_keywords"],
        )
