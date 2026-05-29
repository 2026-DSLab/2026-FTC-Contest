import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path="data/processed/chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_collection("resolutions")

# 1. 총 청크 수 확인
print(f"총 청크 수: {collection.count()}")

# 2. 샘플 1개 확인 (메타데이터 포함)
sample = collection.get(limit=1, include=["documents", "metadatas", "embeddings"])
print(f"\n[샘플 청크]")
print(f"ID: {sample['ids'][0]}")
print(f"내용: {sample['documents'][0][:100]}...")
print(f"메타데이터: {sample['metadatas'][0]}")
print(f"임베딩 차원: {len(sample['embeddings'][0])}")

# 3. 메타데이터 필터링 테스트
print(f"\n[메타데이터 필터링 테스트]")
results = collection.get(
    where={"위반유형": "단체-경쟁제한행위"},
    limit=3,
    include=["metadatas"]
)
print(f"'단체-경쟁제한행위' 청크 수: {len(results['ids'])}")
for meta in results['metadatas']:
    print(f"  - {meta['의결서제목'][:30]}... | {meta['위반유형']}")


# python scripts/test_chroma_db.py
