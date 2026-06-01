from fastapi import APIRouter, HTTPException
from models import FinalReport, SituationType
from agent_pipeline import LegalAnalysisPipeline

router = APIRouter()

# 이벤트 루프 시작 전(모듈 임포트 시점)에 초기화 → Rust/asyncio 충돌 방지
_pipeline = LegalAnalysisPipeline()


@router.post("/diagnose", response_model=FinalReport)
def diagnose(user_query: str, situation_type: str = SituationType.SUSPECTED.value):
    try:
        situation = SituationType(situation_type)
    except ValueError:
        valid = [s.value for s in SituationType]
        raise HTTPException(status_code=422, detail=f"situation_type은 다음 중 하나여야 합니다: {valid}")

    return _pipeline.run(user_query, situation_type=situation)
