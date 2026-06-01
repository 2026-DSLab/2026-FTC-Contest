import os
import ssl

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

from FlagEmbedding import BGEM3FlagModel

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
LOCAL_MODEL_PATH = os.path.join(BASE_DIR, "models", "BGE-m3-ko")
REMOTE_MODEL = "dragonkue/BGE-m3-ko"


class Embedder:
    def __init__(self):
        # 로컬 모델 있으면 로컬에서, 없으면 허깅페이스에서
        model_path = LOCAL_MODEL_PATH if os.path.exists(LOCAL_MODEL_PATH) else REMOTE_MODEL
        print(f"임베딩 모델 로드: {model_path}")
        self.model = BGEM3FlagModel(
            model_path,
            use_fp16=True,
            device="cuda",
        )

    def embed(self, texts: list[str]) -> dict:
        output = self.model.encode(
            texts,
            batch_size=12,
            max_length=512,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=True,
        )
        return {
            "dense": output["dense_vecs"].tolist(),
            "sparse": output["lexical_weights"],
            "colbert": output["colbert_vecs"],
        }

    def embed_query(self, query: str) -> dict:
        return self.embed([query])