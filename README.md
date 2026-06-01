# 헤아림 (Hearim) — AI 공정거래 법률 분석 시스템

사용자의 공정거래 법률 질문을 받아 내부 의결서 DB(RAG) + 외부 법령 API(MCP) + 다중 AI 에이전트를 결합하여 위반 위험도와 법리 해석을 제공하는 시스템입니다.

---

## 프로젝트 구조

```
2026-FTC-Contest/
├── backend/                        # 전체 서버 로직
│   ├── main.py                     # FastAPI 앱 진입점
│   ├── models.py                   # 공통 Pydantic 모델 (FinalReport 등)
│   ├── agent_pipeline.py           # 전체 파이프라인 오케스트레이터
│   ├── mcp_retriever.py            # 국가법령정보 API MCP 클라이언트
│   ├── law_server.py               # MCP 서버 (subprocess로 실행)
│   ├── api/
│   │   └── routes.py               # POST /diagnose 엔드포인트
│   ├── agents/                     # 다중 에이전트 시스템
│   │   ├── base_agent.py           # 에이전트 공통 기반 클래스
│   │   ├── law_agent.py            # 법령 해석 에이전트
│   │   ├── resolution_agent.py     # 의결서 해석 에이전트
│   │   ├── precedent_agent.py      # 판례·결정문 해석 에이전트
│   │   ├── case_agent.py           # 사례 기반 해석 에이전트
│   │   └── synthesis_agent.py      # 종합 분석 에이전트
│   ├── rag/                        # RAG 파이프라인
│   │   ├── pipeline.py             # RAG 전체 흐름
│   │   ├── query/
│   │   │   └── query_processor.py  # 쿼리 재작성 + 의도 분류
│   │   ├── db/
│   │   │   ├── resolution_db.py    # 의결서 Chroma DB 구축·조회
│   │   │   └── scenario_db.py      # 시나리오 엑셀 BM25 검색
│   │   ├── ingestion/
│   │   │   └── embedder.py         # BGE-m3-ko 임베딩
│   │   └── retrieval/
│   │       ├── hybrid_search.py    # Dense + BM25 + RRF
│   │       ├── reranker.py         # Cross-Encoder 리랭킹
│   │       └── filter.py           # LLM 시맨틱 필터링
│   └── schemas/
│       └── rag_output.py           # RAGOutput 스키마
│
├── code/
│   └── main.py                     # CLI 진입점
│
├── data/
│   ├── raw/
│   │   ├── resolutions/            # 의결서 JSON 파일 (build_db.py 입력)
│   │   └── scenarios.xlsx          # 공정거래 QA 데이터 (500개)
│   └── processed/
│       └── chroma_db/              # BGE-m3-ko 벡터 DB (31,877개 청크)
│
├── AI활용데이터/                    # 의결서 원본 PDF + JSON (~150개)
├── results/                        # 분석 결과 JSON 자동 저장
├── scripts/
│   ├── build_db.py                 # 의결서 → Chroma DB 구축 (최초 1회)
│   └── test_*.py                   # 컴포넌트별 테스트 스크립트
└── frontend/                       # UI (Streamlit 연동 예정)
```

---

## 동작 흐름

```
사용자 질문 + 상황 유형
        │
        ▼
┌──────────────────────────────────────┐
│  1단계: RAG 파이프라인               │
│  ① 쿼리 재작성 (GPT-4o-mini)        │
│  ② Hybrid Search → Top 20           │
│     Dense(BGE-m3-ko) + BM25 + RRF   │
│  ③ Reranking (ko-reranker) → Top 10 │
│  ④ LLM Filter (GPT-4o-mini) → Top 5 │
│  ⑤ 시나리오 BM25 검색 → Top 3       │
└──────────────────────────────────────┘
        │ 의결서 청크 5건 + 시나리오 3건
        ▼
┌──────────────────────────────────────┐
│  2단계: MCP 검색 (국가법령정보 API)  │
│  법령 / 판례 / 공정위 결정문         │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  3단계: 4개 에이전트 병렬 분석       │
│  법령 해석 / 의결서 해석             │
│  판례 해석 / 사례 기반 해석          │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  4단계: 종합 에이전트                │
│  위험도 판정 + 권고사항 생성         │
└──────────────────────────────────────┘
        │
        ▼
  FinalReport (JSON) → results/ 저장
```

---

## 사용 모델

| 역할 | 모델 |
|---|---|
| 임베딩 | `dragonkue/BGE-m3-ko` (CUDA, fp16) |
| 쿼리 재작성 / LLM 필터 / 에이전트 | `gpt-4o-mini` |
| 리랭킹 | `Dongjin-kr/ko-reranker` (Cross-Encoder) |

---

## 설치 및 실행

### 0. 패키지 설치 (최초 1회)

```bash
pip install -r requirements.txt
pip install mcp
```

### 1. 환경 변수 설정

`.env` 파일에 아래 값을 입력합니다.

```
OPENAI_API_KEY=sk-...
LAW_API_OC=your_id
```

### 2. Chroma DB 구축 (최초 1회)

의결서 JSON 파일이 `data/raw/resolutions/`에 있어야 합니다.

```bash
python scripts/build_db.py
```

### 3-A. CLI 실행

```bash
python code/main.py "자사상품을 검색 결과 상단에 노출시키면 문제가 되나요?" --situation "위반 의심 사항"
```

분석 결과는 `results/YYYYMMDD_HHMMSS.json`으로 자동 저장됩니다.

**상황 유형 선택지:**

| 값 | 설명 |
|---|---|
| `위반 의심 사항` | 위반 여부가 의심되는 상황 (기본값) |
| `거래 진행 중` | 현재 거래가 진행 중인 상황 |
| `계약 체결 전` | 계약 체결 전 사전 검토 |
| `정기 점검` | 내부 준법 점검 |

**추가 옵션:**

```bash
python code/main.py "질문" --situation "위반 의심 사항" \
  --model gpt-4o-mini \   # 사용할 LLM 모델
  --no-parallel \          # 에이전트 순차 실행 (기본: 병렬)
  --output report.json     # 추가 저장 경로 지정
```

### 3-B. FastAPI 서버 실행

```bash
cd backend
uvicorn main:app --reload --port 8000
```

실행 후 `http://localhost:8000/docs`에서 Swagger UI로 테스트 가능합니다.

**엔드포인트:**

```
POST /diagnose
  ?user_query=질문내용
  &situation_type=위반 의심 사항
```

---

## 출력 구조 (FinalReport)

```json
{
  "original_query": "자사상품을 검색 결과 상단에 노출시키면 문제가 되나요?",
  "rewritten_query": "자사상품 검색 결과 상단 노출의 법적 문제",
  "situation_type": "위반 의심 사항",
  "agent_reports": [
    {
      "agent_type": "law",
      "agent_name": "법령 해석 에이전트",
      "analysis": "...",
      "confidence_score": 85,
      "key_findings": ["...", "..."],
      "limitations": "..."
    }
  ],
  "synthesis": "종합 분석 내용",
  "overall_confidence": 75,
  "risk_level": "높음",
  "recommendations": ["...", "..."],
  "caveats": "..."
}
```

**risk_level 기준:** `낮음` / `보통` / `높음` / `매우 높음`

---

## 프롬프트 수정 방법

각 에이전트의 분석 관점이나 말투를 바꾸려면 해당 파일의 `_SYSTEM_PROMPT`를 수정합니다.

| 에이전트 | 파일 |
|---|---|
| 법령 해석 | `backend/agents/law_agent.py` |
| 의결서 해석 | `backend/agents/resolution_agent.py` |
| 판례 해석 | `backend/agents/precedent_agent.py` |
| 사례 기반 해석 | `backend/agents/case_agent.py` |
| 종합 분석 | `backend/agents/synthesis_agent.py` |
