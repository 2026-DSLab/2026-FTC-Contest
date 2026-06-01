import json
import os
from pathlib import Path

import chromadb
from chromadb.config import Settings

from rag.ingestion.embedder import Embedder


class ResolutionDB:
    def __init__(self, db_path: str = "data/processed/chroma_db"):
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                chroma_api_impl="chromadb.api.segment.SegmentAPI",
            ),
        )
        self.collection = self.client.get_or_create_collection(
            name="resolutions",
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = Embedder()

    def build(self, data_dir: str = "data/raw/resolutions"):
        """
        data_dir 안의 hybrid.json + metadata.json 읽어서
        임베딩 생성 후 Chroma DB에 저장
        """
        data_path = Path(data_dir)
        hybrid_files = sorted(data_path.glob("*_hybrid.json"))

        print(f"총 {len(hybrid_files)}개 의결서 처리 시작")

        for idx, hybrid_file in enumerate(hybrid_files):
            # 대응하는 metadata 파일 찾기
            base_name = hybrid_file.stem.replace("_hybrid", "")
            metadata_file = hybrid_file.parent / f"{base_name}_metadata.json"

            if not metadata_file.exists():
                print(f"[SKIP] metadata 없음: {base_name}")
                continue

            # 파일 로드
            with open(hybrid_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            with open(metadata_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            # 피심인 정보 flatten
            pisimin = meta.get("피심인정보", [{}])[0]

            # 청크 배열 순회
            texts = []
            ids = []
            metadatas = []

            for chunk in chunks:
                chunk_meta = chunk.get("metadata", {})
                chunk_id = chunk_meta.get("chunk_id", "")
                content = chunk.get("page_content", "")

                if not content.strip():
                    continue

                texts.append(content)
                ids.append(chunk_id)
                metadatas.append({
                    # 의결서 메타
                    "의결서관리번호": meta.get("의결서관리번호", ""),
                    "의결서제목": meta.get("의결서제목", ""),
                    "공개일자": meta.get("공개일자", ""),
                    # 피심인 메타
                    "위반유형": pisimin.get("위반유형", ""),
                    "세부위반유형": pisimin.get("세부위반유형", ""),
                    "조치유형": pisimin.get("조치유형", ""),
                    "피심인기업명": pisimin.get("피심인기업명", ""),
                    # 청크 메타
                    "section": chunk_meta.get("section", ""),
                    "chunk_type": chunk_meta.get("chunk_type", ""),
                    "chunk_index": chunk_meta.get("chunk_index", 0),
                })

            if not texts:
                continue

            # 임베딩 생성 (배치 단위)
            embeddings = self.embedder.embed(texts)
            dense_vecs = embeddings["dense"]

            # Chroma에 저장
            self.collection.upsert(
                ids=ids,
                documents=texts,
                embeddings=dense_vecs,
                metadatas=metadatas,
            )

            print(f"[{idx+1}/500] {base_name[:30]}... ({len(texts)}개 청크 저장)")

        print("DB 구축 완료")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        where: dict = None,
    ) -> list[dict]:
        """Dense 벡터 기반 검색"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        for i in range(len(results["ids"][0])):
            docs.append({
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "score": 1 - results["distances"][0][i],  # cosine → 유사도
                "metadata": results["metadatas"][0][i],
            })
        return docs