import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from agent_pipeline import LegalAnalysisPipeline
from models import SituationType
from rag.query.query_processor import IrrelevantQueryError

router = APIRouter()
pipeline = LegalAnalysisPipeline()

_RESULTS_DIR = Path(__file__).parent.parent.parent / "results"
_RESULTS_DIR.mkdir(exist_ok=True)

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
    
    try:
        result = pipeline.run(req.user_query, situation_type=situation, verbose=True)
        pipeline_trace = {}
    except IrrelevantQueryError as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = result.model_dump()

    # results/ 에 저장
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = req.user_query[:20].replace(" ", "_").replace("/", "-")
    save_path = _RESULTS_DIR / f"{ts}_{slug}.json"
    save_data = {**data, "_pipeline_trace": pipeline_trace}
    save_path.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return JSONResponse(content=data)

@router.get("/diagnose_stream")
async def diagnose_stream(query: str, situation: str):
    situation_str = SITUATION_MAP.get(situation, situation)
    
    try:
        situation_type_obj = SituationType(situation_str)
    except ValueError:
        valid = list(SITUATION_MAP.keys())
        raise HTTPException(status_code=422, detail=f"situation은 다음 중 하나: {valid}")

    async def event_generator():
        try:
            async for chunk in pipeline.run_stream(query, situation_type=situation_type_obj):
                yield f"data: {chunk}\n\n"
        except IrrelevantQueryError as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'서버 오류: {str(e)}'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")