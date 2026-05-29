import os
import ssl

# 학교 네트워크 SSL 우회 (반드시 다른 import보다 먼저)
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
ssl._create_default_https_context = ssl._create_unverified_context

# httpx 패치
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

# requests 패치
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
_orig_session_init = requests.Session.__init__
def _patched_session(self, *a, **kw):
    _orig_session_init(self, *a, **kw)
    self.verify = False
requests.Session.__init__ = _patched_session
requests.packages.urllib3.disable_warnings()

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from rag.db.resolution_db import ResolutionDB

if __name__ == "__main__":
    db = ResolutionDB(db_path="data/processed/chroma_db")
    db.build(data_dir="data/raw/resolutions")