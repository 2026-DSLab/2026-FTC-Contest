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

SYSTEM_PROMPT = """당신은 공정거래 법률 전문가입니다.
사용자 질문과 검색된 문서 목록이 주어집니다.
각 문서가 사용자 질문과 실질적으로 관련이 있는지 판단하여
관련 있는 문서의 인덱스만 JSON 배열로 반환하세요.

최대 5개까지만 선택하세요.
관련도가 낮은 문서는 과감히 제외하세요.

반드시 아래 JSON 형식으로만 답하세요:
{"relevant_indices": [0, 1, 2, ...]}"""


async def llm_filter(query: str, docs: list[dict], top_k: int = 5) -> list[dict]:
    # 문서 목록 구성
    doc_list = ""
    for i, doc in enumerate(docs):
        doc_list += f"\n[{i}] {doc['content'][:500]}...\n"

    user_message = f"사용자 질문: {query}\n\n문서 목록:{doc_list}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        result = json.loads(response.choices[0].message.content)
        relevant_indices = result.get("relevant_indices")
        if not isinstance(relevant_indices, list):
            raise ValueError(f"relevant_indices 형식 오류: {relevant_indices}")
    except Exception as e:
        print(f"[filter] LLM 필터 실패, 빈 결과 반환: {e}")
        return []

    # top_k 초과하면 앞에서 자르기
    relevant_indices = relevant_indices[:top_k]

    return [docs[i] for i in relevant_indices if i < len(docs)]