from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agent_pipeline import LegalAnalysisPipeline
from models import SituationType

router = APIRouter()
pipeline = LegalAnalysisPipeline()

# 영어 → 한글 매핑
SITUATION_MAP = {
    "suspected": "위반 의심 사항",
    "in_progress": "거래 진행 중",
    "contract_before": "계약 체결 전",
    "regular_check": "정기 점검"
}

class DiagnoseRequest(BaseModel):
    user_query: str
    situation_type: str

@router.post("/diagnose")
def diagnose(req: DiagnoseRequest):
    # 영어로 오면 한글로 변환
    situation_str = SITUATION_MAP.get(req.situation_type, req.situation_type)
    
    try:
        situation = SituationType(situation_str)
    except ValueError:
        valid = list(SITUATION_MAP.keys())
        raise HTTPException(status_code=422, detail=f"situation_type은 다음 중 하나: {valid}")
    
    result = pipeline.run(req.user_query, situation_type=situation)
    return JSONResponse(content=result.model_dump())