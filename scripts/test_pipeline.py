import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

import asyncio
import json
from rag.pipeline import RAGPipeline

pipeline = RAGPipeline(
    db_path="data/processed/chroma_db",
    excel_path="data/raw/scenarios.xlsx"
)

result = asyncio.get_event_loop().run_until_complete(
    pipeline.run(
        user_query="자사상품 검색 상단에 올리면 문제되나요?",
        situation_type="suspected"
    )
)

# JSON 직렬화
result_json = json.loads(result.model_dump_json())
print(json.dumps(result_json, ensure_ascii=False, indent=2))