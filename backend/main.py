from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "backend"))

from rag.query.query_processor import process_query
from api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 API 워밍업
    print("API 워밍업 중...")
    await process_query("워밍업")
    print("API 워밍업 완료")
    yield


app = FastAPI(title="헤아림 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# 프론트엔드 정적 파일 서빙
frontend_dir = os.path.join(BASE_DIR, "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")