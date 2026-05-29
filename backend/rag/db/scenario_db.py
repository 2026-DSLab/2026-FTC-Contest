import pandas as pd
from rank_bm25 import BM25Okapi

from rag.ingestion.excel_loader import load_scenarios, filter_by_situation


class ScenarioDB:
    def __init__(self, excel_path: str):
        self.df = load_scenarios(excel_path)

    def search(self, query: str, situation_type: str, top_k: int = 3) -> list[dict]:
        # situation_type 필터링
        filtered = filter_by_situation(self.df, situation_type)

        if filtered.empty:
            return []

        # 질문 + 답변 합쳐서 BM25 검색
        corpus = (filtered["질문"].fillna("") + " " + filtered["답변"].fillna("")).tolist()
        tokenized_corpus = [doc.split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)

        tokenized_query = query.split()
        scores = bm25.get_scores(tokenized_query)

        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            row = filtered.iloc[idx]
            results.append({
                "question": str(row["질문"]),
                "answer": str(row["답변"]),
                "legal_interpretation": str(row["법리 해석"]) if pd.notna(row["법리 해석"]) else "",
                "evidence": str(row["근거"]) if pd.notna(row["근거"]) else "",
                "situation_type": situation_type,
                "score": scores[idx]
            })

        return results