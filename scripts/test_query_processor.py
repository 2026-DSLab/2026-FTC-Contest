import sys
import os
import asyncio
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from rag.query.query_processor import process_query

async def main():
    test_queries = [
        "자사상품 검색 상단에 올리면 문제되나요?",
        "납품업자에게 판촉비를 부담시키면 과징금이 얼마나 나와요?",
        "우리 회사 계약서에 경업금지 3년 넣으면 괜찮을까요?",
    ]

    for query in test_queries:
        print(f"\n입력: {query}")
        result = await process_query(query)
        print(f"재작성: {result['rewritten_query']}")
        print(f"의도: {result['intent']}")

asyncio.run(main())