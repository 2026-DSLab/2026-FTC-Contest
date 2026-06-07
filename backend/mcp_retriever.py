"""
Step 2: External Knowledge Retrieval via MCP
law_server.py MCP 서버에 연결하여 법령/판례/공정위 결정문을 검색합니다.
"""
from __future__ import annotations

import asyncio
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from models import ExternalEvidence, LawDocument

LAW_SERVER_PATH = Path(__file__).parent / "law_server.py"

# 검색 결과 개수 (필요시 조정)
SEARCH_DISPLAY = 5
# 본문 가져올 최대 문서 수
MAX_DETAIL_FETCH = 3


def _parse_search_results(xml_text: str) -> list[dict[str, str]]:
    """MCP 서버가 반환하는 XML에서 검색 결과 목록을 파싱합니다."""
    try:
        import re
        xml_text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", xml_text)
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    skip = {"totalCnt", "pageSize", "pageIndex", "query", "numOfRows"}
    results = []
    for child in root:
        if child.tag not in skip:
            item = {sub.tag: (sub.text or "").strip() for sub in child}
            if item:
                results.append(item)
    return results


class MCPRetriever:
    """MCP 서버(law_server.py)를 subprocess로 실행하고 도구를 호출합니다."""

    def __init__(self, display: int = SEARCH_DISPLAY, max_detail: int = MAX_DETAIL_FETCH):
        self.display = display
        self.max_detail = max_detail
        self._server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(LAW_SERVER_PATH)],
            env={**os.environ, "LAW_API_OC": os.environ.get("LAW_API_OC", "sgrhee3")},
        )

    async def _call_tool(self, session: ClientSession, name: str, args: dict[str, Any]) -> str:
        result = await session.call_tool(name, args)
        texts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(texts)

    async def retrieve(self, law_query: str, prec_query: str) -> ExternalEvidence:
        """법령·판례를 각각 최적화된 쿼리로 검색합니다.
        - law_query: 법령명 검색용 (예: "독점규제 공정거래")
        - prec_query: 판례 본문 검색용 (예: "자사우대 불공정거래 부당한 고객유인")
        """
        evidence = ExternalEvidence()

        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # ── 법령 검색 ──────────────────────────────────
                law_xml = await self._call_tool(
                    session, "search_law", {"query": law_query, "display": self.display}
                )
                laws = _parse_search_results(law_xml)
                for item in laws[: self.max_detail]:
                    mst = item.get("법령일련번호") or item.get("MST") or item.get("mst")
                    # XML 태그: 법령명한글 (언더스코어 없음)
                    title = item.get("법령명한글") or item.get("법령명") or item.get("title", "")
                    if mst:
                        content_xml = await self._call_tool(
                            session, "get_law_content", {"mst": mst}
                        )
                        evidence.laws.append(
                            LawDocument(doc_type="law", title=title, content=content_xml, source_id=mst)
                        )
                    elif title:
                        evidence.laws.append(
                            LawDocument(doc_type="law", title=title, content=str(item))
                        )

                # ── 판례 검색 ──────────────────────────────────
                prec_xml = await self._call_tool(
                    session, "search_precedent", {"query": prec_query, "display": self.display}
                )
                precs = _parse_search_results(prec_xml)
                for item in precs[: self.max_detail]:
                    pid = item.get("판례일련번호") or item.get("ID") or item.get("id")
                    title = item.get("사건명") or item.get("판례명") or item.get("title", "")
                    if pid:
                        content_xml = await self._call_tool(
                            session, "get_precedent_content", {"prec_id": pid}
                        )
                        evidence.precedents.append(
                            LawDocument(doc_type="precedent", title=title, content=content_xml, source_id=pid)
                        )
                    elif title:
                        evidence.precedents.append(
                            LawDocument(doc_type="precedent", title=title, content=str(item))
                        )

        return evidence

    def retrieve_sync(self, law_query: str, prec_query: str) -> ExternalEvidence:
        """동기 래퍼 (이미 이벤트 루프가 있을 경우 asyncio.run 대신 사용)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.retrieve(law_query, prec_query))
                    return future.result()
            else:
                return loop.run_until_complete(self.retrieve(law_query, prec_query))
        except RuntimeError:
            return asyncio.run(self.retrieve(law_query, prec_query))
