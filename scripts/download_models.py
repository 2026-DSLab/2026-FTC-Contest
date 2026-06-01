import os
import ssl

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

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# 1. BGE-m3-ko 임베딩 모델 (huggingface_hub으로 다운)
print("BGE-m3-ko 다운로드 중...")
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="dragonkue/BGE-m3-ko",
    local_dir=os.path.join(MODELS_DIR, "BGE-m3-ko"),
    ignore_patterns=["*.msgpack", "*.h5", "flax_model*"]
)
print("BGE-m3-ko 저장 완료")

# 2. ko-reranker 리랭킹 모델
print("ko-reranker 다운로드 중...")
snapshot_download(
    repo_id="Dongjin-kr/ko-reranker",
    local_dir=os.path.join(MODELS_DIR, "ko-reranker"),
    ignore_patterns=["*.msgpack", "*.h5", "flax_model*"]
)
print("ko-reranker 저장 완료")

print("\n모든 모델 다운로드 완료!")
print(f"저장 경로: {MODELS_DIR}")