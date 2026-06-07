import os
from rank_bm25 import BM25Okapi
import chromadb
from chromadb.config import Settings

from rag.ingestion.embedder import Embedder


class HybridSearch:
    def __init__(self, db_path: str = "data/processed/chroma_db"):
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_collection("resolutions")
        self.embedder = Embedder()

        print("BM25 인덱스 구축 중...")
        all_docs = self.collection.get(include=["documents", "metadatas"])
        self.all_ids = all_docs["ids"]
        self.all_docs = all_docs["documents"]
        self.all_metadatas = all_docs["metadatas"]

        tokenized_corpus = [doc.split() for doc in self.all_docs]
        self.bm25 = BM25Okapi(tokenized_corpus)
        print(f"BM25 인덱스 구축 완료 ({len(self.all_ids)}개 청크)")

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        # 1. Dense 검색
        query_embedding = self.embedder.embed_query(query)
        dense_results = self.collection.query(
            query_embeddings=[query_embedding["dense"][0]],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        dense_docs = {}
        for i, doc_id in enumerate(dense_results["ids"][0]):
            dense_docs[doc_id] = {
                "chunk_id": doc_id,
                "content": dense_results["documents"][0][i],
                "metadata": dense_results["metadatas"][0][i],
                "dense_rank": i + 1
            }

        # 2. BM25 검색
        tokenized_query = query.split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_bm25_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[:top_k]

        bm25_docs = {}
        for rank, idx in enumerate(top_bm25_indices):
            doc_id = self.all_ids[idx]
            bm25_docs[doc_id] = {
                "chunk_id": doc_id,
                "content": self.all_docs[idx],
                "metadata": self.all_metadatas[idx],
                "bm25_rank": rank + 1
            }

        # 3. RRF 결합
        k = 60
        all_ids = set(dense_docs.keys()) | set(bm25_docs.keys())

        rrf_scores = {}
        for doc_id in all_ids:
            score = 0
            if doc_id in dense_docs:
                score += 1 / (k + dense_docs[doc_id]["dense_rank"])
            if doc_id in bm25_docs:
                score += 1 / (k + bm25_docs[doc_id]["bm25_rank"])
            rrf_scores[doc_id] = score

        # 4. RRF 스코어 기준 정렬 후 top_k 반환
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        results = []
        for doc_id in sorted_ids:
            dense_entry = dense_docs.get(doc_id)
            bm25_entry = bm25_docs.get(doc_id)
            doc = dense_entry or bm25_entry
            results.append({
                "chunk_id": doc["chunk_id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "score": rrf_scores[doc_id],
                "dense_rank": dense_entry["dense_rank"] if dense_entry else None,
                "bm25_rank": bm25_entry["bm25_rank"] if bm25_entry else None,
            })

        return results