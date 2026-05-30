from FlagEmbedding import BGEM3FlagModel

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import os
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"



class Embedder:
    def __init__(self):
        self.model = BGEM3FlagModel(
            "dragonkue/BGE-m3-ko",
            use_fp16=True,  # CUDA 환경에서 속도 향상
            device="cuda",
        )

    def embed(self, texts: list[str]) -> dict:
        """
        반환값:
        {
            "dense":  List[List[float]],   # Dense 벡터 (Chroma 저장용)
            "sparse": List[dict],          # Sparse 벡터 (BM25 대체, Hybrid용)
            "colbert": List[List[float]]   # ColBERT 벡터 (Re-ranking용)
        }
        """
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
        """단일 쿼리 임베딩"""
        return self.embed([query])