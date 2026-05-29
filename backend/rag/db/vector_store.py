# 벡터 DB 관리 (Chroma)
# 벡터 저장 / 조회


class VectorStore:
    def __init__(self, db_path: str):
        # TODO: Chroma 초기화
        pass

    def add(self, chunks: list[str], embeddings: list[list[float]], metadata: list[dict]):
        # TODO: 벡터 저장
        pass

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        # TODO: 유사도 검색
        pass
