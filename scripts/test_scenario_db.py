import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from rag.db.scenario_db import ScenarioDB

db = ScenarioDB(excel_path="data/raw/scenarios.xlsx")

results = db.search(
    query="자사상품 검색 결과 상단 노출하면 문제되나요",
    situation_type="suspected",
    top_k=3
)

for i, r in enumerate(results):
    print(f"\n[{i+1}]")
    print(f"질문: {r['question'][:50]}...")
    print(f"답변: {r['answer'][:80]}...")
    print(f"법리해석: {r['legal_interpretation'][:80]}...")
    print(f"근거: {r['evidence']}")
    print(f"상황유형: {r['situation_type']}")
    print(f"스코어: {r['score']:.4f}")

# python scripts/test_scenario_db.py