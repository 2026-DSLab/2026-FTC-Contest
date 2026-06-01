import asyncio
import httpx
import xml.etree.ElementTree as ET
import sys
import logging
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# 반드시 stderr로만 로깅 (stdout은 MCP 프로토콜 전용)
logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

OC_ID = os.environ.get("LAW_API_OC", "sgrhee3")
BASE_URL = "http://www.law.go.kr/DRF/lawSearch.do"
DETAIL_URL = "http://www.law.go.kr/DRF/lawService.do"

app = Server("law-kr-mcp")


def parse_xml_to_dict(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # XML 파싱 실패시 특수문자 정리 후 재시도
        import re
        xml_text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', xml_text)
        root = ET.fromstring(xml_text)

    skip_tags = {"totalCnt", "pageSize", "pageIndex", "query", "numOfRows"}
    results = []
    for child in root:
        if child.tag not in skip_tags:
            item = {sub.tag: (sub.text or "").strip() for sub in child}
            if item:
                results.append(item)
    return results


async def fetch_api(base: str, params: dict) -> str:
    params["OC"] = OC_ID
    params["type"] = "XML"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(base, params=params)
        resp.raise_for_status()
        content = resp.content
        for encoding in ["euc-kr", "utf-8", "cp949"]:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", errors="replace")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_law",
            description="법령(법률/대통령령/시행규칙 등) 목록을 키워드로 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "page": {"type": "integer", "default": 1},
                    "display": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_law_content",
            description="법령 일련번호(MST)로 법령 본문을 가져옵니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mst": {"type": "string"},
                },
                "required": ["mst"],
            },
        ),
        types.Tool(
            name="search_precedent",
            description="판례를 키워드로 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "page": {"type": "integer", "default": 1},
                    "display": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_precedent_content",
            description="판례 일련번호로 판례 전문을 가져옵니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prec_id": {"type": "string"},
                },
                "required": ["prec_id"],
            },
        ),
        types.Tool(
            name="search_ftc_decision",
            description="공정거래위원회 결정문을 키워드로 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "page": {"type": "integer", "default": 1},
                    "display": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_ftc_decision_content",
            description="공정위 결정문 일련번호로 결정문 전문을 가져옵니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cmt_id": {"type": "string"},
                },
                "required": ["cmt_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "search_law":
            xml = await fetch_api(BASE_URL, {
                "target": "law",
                "query": arguments["query"],
                "page": arguments.get("page", 1),
                "display": arguments.get("display", 10),
            })
            return [types.TextContent(type="text", text=xml)]

        elif name == "get_law_content":
            xml = await fetch_api(DETAIL_URL, {
                "target": "lawService",
                "MST": arguments["mst"],
            })
            return [types.TextContent(type="text", text=xml[:8000])]

        elif name == "search_precedent":
            xml = await fetch_api(BASE_URL, {
                "target": "prec",
                "query": arguments["query"],
                "page": arguments.get("page", 1),
                "display": arguments.get("display", 10),
                "search": 2,
            })
            return [types.TextContent(type="text", text=xml)]

        elif name == "get_precedent_content":
            xml = await fetch_api(DETAIL_URL, {
                "target": "precService",
                "ID": arguments["prec_id"],
            })
            return [types.TextContent(type="text", text=xml[:8000])]

        elif name == "search_ftc_decision":
            xml = await fetch_api(BASE_URL, {
                "target": "cmt",
                "query": arguments["query"],
                "page": arguments.get("page", 1),
                "display": arguments.get("display", 10),
            })
            return [types.TextContent(type="text", text=xml)]

        elif name == "get_ftc_decision_content":
            xml = await fetch_api(DETAIL_URL, {
                "target": "cmtService",
                "ID": arguments["cmt_id"],
            })
            return [types.TextContent(type="text", text=xml[:8000])]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        log.exception("Tool error")
        return [types.TextContent(type="text", text=f"Error: {e}")]

async def main():
    log.info("Starting law-kr MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
