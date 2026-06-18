import json
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from agent_pipeline import LegalAnalysisPipeline
from models import SituationType
from rag.query.query_processor import process_query, IrrelevantQueryError

router = APIRouter()
pipeline = LegalAnalysisPipeline()
diagnose_jobs = {}

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


def _resolve_situation(value: str) -> SituationType:
    situation_str = SITUATION_MAP.get(value, value)
    try:
        return SituationType(situation_str)
    except ValueError:
        valid = list(SITUATION_MAP.keys())
        raise HTTPException(status_code=422, detail=f"situation_type은 다음 중 하나: {valid}")


async def _run_diagnose_job(job_id: str, query: str, situation: SituationType):
    diagnose_jobs[job_id] = {
        "status": "processing",
        "step": 1,
        "message": "1/4 쿼리 재작성 중...",
        "data": None,
    }

    try:
        async for chunk in pipeline.run_stream(query, situation_type=situation):
            payload = json.loads(chunk)
            if payload.get("status") == "processing":
                diagnose_jobs[job_id] = {
                    "status": "processing",
                    "step": payload.get("step"),
                    "message": payload.get("message"),
                    "data": None,
                }
            elif payload.get("status") == "complete":
                result_data = payload.get("data")
                pipeline_trace = payload.get("pipeline_trace", {})
                diagnose_jobs[job_id] = {
                    "status": "complete",
                    "step": 4,
                    "message": "진단 결과 생성이 완료되었습니다.",
                    "data": result_data,
                }
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                slug = query[:20].replace(" ", "_").replace("/", "-")
                save_path = _RESULTS_DIR / f"{ts}_{slug}.json"
                save_data = {**result_data, "_pipeline_trace": pipeline_trace}
                save_path.write_text(json.dumps(save_data, ensure_ascii=False, indent=2), encoding="utf-8")
            elif payload.get("status") == "error":
                diagnose_jobs[job_id] = {
                    "status": "error",
                    "step": payload.get("step"),
                    "message": payload.get("message", "진단 중 오류가 발생했습니다."),
                    "data": None,
                }
    except IrrelevantQueryError as e:
        diagnose_jobs[job_id] = {
            "status": "error",
            "step": 1,
            "message": str(e),
            "data": None,
        }
    except Exception as e:
        diagnose_jobs[job_id] = {
            "status": "error",
            "step": None,
            "message": f"서버 오류: {str(e)}",
            "data": None,
        }

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
        result, pipeline_trace = pipeline.run_traced(req.user_query, situation_type=situation, verbose=True)
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


@router.post("/diagnose_start")
async def diagnose_start(req: DiagnoseRequest):
    situation = _resolve_situation(req.situation_type)
    job_id = uuid.uuid4().hex
    diagnose_jobs[job_id] = {
        "status": "processing",
        "step": 1,
        "message": "1/4 쿼리 재작성 중...",
        "data": None,
    }
    asyncio.create_task(_run_diagnose_job(job_id, req.user_query, situation))
    return JSONResponse(content={"job_id": job_id})


@router.get("/diagnose_status/{job_id}")
async def diagnose_status(job_id: str):
    job = diagnose_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="진단 작업을 찾을 수 없습니다.")
    return JSONResponse(content=job)

@router.post("/validate_query")
async def validate_query(req: DiagnoseRequest):
    situation_str = SITUATION_MAP.get(req.situation_type, req.situation_type)
    try:
        situation = SituationType(situation_str)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid situation_type")
        
    try:
        # 쿼리 재작성 모듈을 직접 호출하여 관련성이 있는지 검증
        await process_query(req.user_query)
        return JSONResponse(content={"status": "ok"})
    except IrrelevantQueryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

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
            yield ": connected\n\n"
            async for chunk in pipeline.run_stream(query, situation_type=situation_type_obj):
                yield f"data: {chunk}\n\n"
        except IrrelevantQueryError as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'서버 오류: {str(e)}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
