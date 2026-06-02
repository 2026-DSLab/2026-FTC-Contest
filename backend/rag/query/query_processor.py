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
사용자의 질문을 분석하여 다음 세 가지를 JSON으로 반환하세요.

1. is_relevant: 질문이 공정거래·경쟁법·기업 컴플라이언스 관련인지 여부 (true/false)
   - true: 불공정거래, 과징금, 하도급, 가맹사업, 표시광고, 공동행위, 거래상 지위남용,
           계약 법적 리스크, 기업 간 거래 분쟁 등 공정거래 관련 주제
   - false: 요리, 날씨, 스포츠, 코딩, 일반 상식 등 공정거래와 전혀 무관한 주제

2. rewritten_query: 법률 검색에 최적화된 형태로 재작성한 쿼리 (is_relevant=true일 때만 의미 있음)
   - 법률 용어를 포함
   - 핵심 쟁점이 드러나도록 구체화
   - 50자 이내

3. intent: 질문 의도 분류 (아래 4가지 중 하나, is_relevant=true일 때만 의미 있음)
   - "제재중심": 제재, 과징금, 처벌 수준 관련
   - "법령중심": 법령, 조문, 위반 여부 관련
   - "유사사례": 유사한 사례, 판례 관련
   - "시장영향": 시장, 경쟁, 소비자 영향 관련

반드시 아래 JSON 형식으로만 답하세요:
{"is_relevant": true, "rewritten_query": "...", "intent": "..."}"""


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
        "intent": result.get("intent", "법령중심")
    }