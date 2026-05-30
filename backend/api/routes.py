from fastapi import APIRouter
from schemas.rag_output import RAGOutput
from schemas.report_output import ReportOutput
from rag.pipeline import run_rag_pipeline

router = APIRouter()


@router.post("/diagnose", response_model=ReportOutput)
async def diagnose(user_query: str, situation_type: str):
    # 1. RAG 파이프라인 실행 (서준원)
    rag_output: RAGOutput = await run_rag_pipeline(user_query, situation_type)

    # 2. 에이전트 실행 (이승건) - 추후 연결
    # report = await run_agents(rag_output)

    pass
