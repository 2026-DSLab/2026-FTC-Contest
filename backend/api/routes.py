from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio
import sys
import os

# 프로젝트 루트 기준 경로
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.append(os.path.join(BASE_DIR, "backend"))

from rag.pipeline import RAGPipeline
from schemas.rag_output import RAGOutput

router = APIRouter()

pipeline = RAGPipeline(
    db_path=os.path.join(BASE_DIR, "data/processed/chroma_db"),
    excel_path=os.path.join(BASE_DIR, "data/raw/scenarios.xlsx")
)

class DiagnoseRequest(BaseModel):
    user_query: str
    situation_type: str


@router.post("/diagnose")
async def diagnose(req: DiagnoseRequest):
    result: RAGOutput = await pipeline.run(
        user_query=req.user_query,
        situation_type=req.situation_type
    )
    return JSONResponse(content=result.model_dump())