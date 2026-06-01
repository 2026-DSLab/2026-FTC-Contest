import os
import ssl
import asyncio

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

import torch
from sentence_transformers import CrossEncoder

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOCAL_MODEL_PATH = os.path.join(BASE_DIR, "models", "ko-reranker")
REMOTE_MODEL = "Dongjin-kr/ko-reranker"


class Reranker:
    def __init__(self):
        model_path = LOCAL_MODEL_PATH if os.path.exists(LOCAL_MODEL_PATH) else REMOTE_MODEL
        print(f"리랭커 모델 로드: {model_path}")
        self.model = CrossEncoder(
            model_path,
            device="cuda",
            automodel_args={"torch_dtype": torch.float16}
        )

        # CUDA 워밍업
        print("리랭커 워밍업 중...")
        self.model.predict([("워밍업 쿼리", "워밍업 문서")])
        print("리랭커 워밍업 완료")

    def rerank(self, query: str, docs: list[dict], top_k: int = 5) -> list[dict]:
        pairs = [(query, doc["content"]) for doc in docs]
        scores = self.model.predict(pairs, batch_size=32)

        for i, doc in enumerate(docs):
            doc["rerank_score"] = float(scores[i])

        reranked = sorted(docs, key=lambda x: x["rerank_score"], reverse=True)[:top_k]
        return reranked

    async def rerank_async(self, query: str, docs: list[dict], top_k: int = 5) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.rerank(query, docs, top_k)
        )