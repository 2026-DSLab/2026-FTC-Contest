import os
import ssl
import json

# 학교 네트워크 SSL 우회
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context

import httpx
_orig_client_init = httpx.Client.__init__
_orig_async_init  = httpx.AsyncClient.__init__
def _patched_client(self, *a, **kw):
    kw["verify"] = False
    _orig_client_init(self, *a, **kw)
def _patched_async(self, *a, **kw):
    kw["verify"] = False
    _orig_async_init(self, *a, **kw)
httpx.Client.__init__      = _patched_client
httpx.AsyncClient.__init__ = _patched_async

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
_orig_session_init = requests.Session.__init__
def _patched_session(self, *a, **kw):
    _orig_session_init(self, *a, **kw)
    self.verify = False
requests.Session.__init__ = _patched_session
requests.packages.urllib3.disable_warnings()

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class IrrelevantQueryError(Exception):
    """공정거래와 무관한 질문일 때 발생하는 예외"""
    pass


SYSTEM_PROMPT = """당신은 공정거래 법률 전문가입니다.
사용자의 질문을 분석하여 다음 다섯 가지를 JSON으로 반환하세요.

1. is_relevant: 질문이 공정거래·경쟁법·기업 컴플라이언스 관련인지 여부 (true/false)
   - true: 독점규제 및 공정거래법, 하도급법, 가맹사업법, 대리점법, 표시광고법, 약관법, 전자상거래법 등 공정거래 규제 법률이나 기업의 계약 검토, 준법 준수(컴플라이언스) 및 비즈니스 거래상의 법적 리스크 분석에 관한 주제
   - false: 요리, 날씨, 스포츠, 코딩, 일반 상식 등 공정거래와 전혀 무관한 주제

2. rewritten_query: RAG 의결서 검색에 최적화된 형태로 재작성한 쿼리 (is_relevant=true일 때만 의미 있음)
   - 법률 용어를 포함
   - 핵심 쟁점이 드러나도록 구체화
   - 50자 이내

3. intent: 질문 의도 분류 (아래 4가지 중 하나, is_relevant=true일 때만 의미 있음)
   - "제재중심": 제재, 과징금, 처벌 수준 관련
   - "법령중심": 법령, 조문, 위반 여부 관련
   - "유사사례": 유사한 사례, 판례 관련
   - "시장영향": 시장, 경쟁, 소비자 영향 관련

4. mcp_law_query: 법령 이름 검색에 최적화된 키워드 (is_relevant=true일 때만 의미 있음)
   - law.go.kr 법령명(lawNm) 검색이므로 반드시 실제 법령 공식 명칭이나 약칭을 사용해야 함
   - 공정거래·플랫폼·자사우대·검색순위·불공정거래·시장지배적지위 관련 → "독점규제 공정거래"
   - 하도급 관련 → "하도급거래", 가맹 관련 → "가맹사업", 대규모유통 관련 → "대규모유통업"
   - "표시광고"는 표시광고법 직접 위반 사안에만 사용 (검색노출·자사우대는 공정거래법 사안)
   - 15자 이내 핵심 법령명

5. mcp_prec_query: 판례 본문 검색에 최적화된 키워드 (is_relevant=true일 때만 의미 있음)
   - 판례 본문(bdyText)에서 검색되므로 핵심 법리·행위 유형을 포함
   - 예: "자사우대 불공정거래 부당한 고객유인", "하도급 기술자료 유용", "가맹본부 부당한 거래거절"
   - 20자 이내 핵심 법리 표현

반드시 아래 JSON 형식으로만 답하세요:
{"is_relevant": true, "rewritten_query": "...", "intent": "...", "mcp_law_query": "...", "mcp_prec_query": "..."}"""


async def process_query(user_query: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        response_format={"type": "json_object"},
        temperature=0
    )

    result = json.loads(response.choices[0].message.content)

    if not result.get("is_relevant", True):
        raise IrrelevantQueryError(
            "공정거래·기업 컴플라이언스와 관련된 질문만 답변할 수 있습니다. "
            "불공정거래, 계약 리스크, 과징금, 하도급·가맹·표시광고 등 관련 주제로 질문해 주세요."
        )

    return {
        "rewritten_query": result.get("rewritten_query", user_query),
        "intent": result.get("intent", "법령중심"),
        "mcp_law_query": result.get("mcp_law_query", "독점규제 공정거래"),
        "mcp_prec_query": result.get("mcp_prec_query", result.get("rewritten_query", user_query)),
    }