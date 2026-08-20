# 헤아림 (Hearim) — AI 공정거래 법률 분석 시스템

<img width="600" height="285" alt="KakaoTalk_20260820_131505190" src="https://github.com/user-attachments/assets/d2f7c776-ca9f-4a1e-a43f-8535e1ac86ec" />
사용자의 공정거래 법률 질문을 받아 내부 의결서 DB(RAG) + 외부 법령 API(MCP) + 다중 AI 에이전트를 결합하여 위반 위험도와 법리 해석을 제공하는 시스템입니다.

---

## 프로젝트 구조

```
hearim/
├── frontend/                       # 웹 화면
│   ├── 질문화면.html                # 질문 입력 화면 (FastAPI 연결)
│   ├── 결과화면_더미.html           # 더미 테스트용 (RAG JSON 출력)
│   ├── 결과화면(예시).html          # 하드코딩 예시 화면
│   └── 헤아림.jpg
│
├── backend/
│   ├── main.py                     # FastAPI 진입점 (서버 시작 + API 워밍업)
│   ├── models.py                   # 공통 Pydantic 모델 (FinalReport 등)
│   ├── agent_pipeline.py           # 전체 파이프라인 오케스트레이터
│   ├── mcp_retriever.py            # 국가법령정보 API MCP 클라이언트
│   ├── law_server.py               # MCP 서버 (subprocess로 실행)
│   ├── api/
│   │   └── routes.py               # API 엔드포인트 (/diagnose)
│   ├── agents/                     # 다중 에이전트 시스템
│   │   ├── base_agent.py
│   │   ├── law_agent.py            # 법령 해석 에이전트
│   │   ├── resolution_agent.py     # 의결서 해석 에이전트
│   │   ├── precedent_agent.py      # 판례·결정문 해석 에이전트
│   │   ├── case_agent.py           # 사례 기반 해석 에이전트
│   │   └── synthesis_agent.py      # 종합 분석 에이전트
│   ├── rag/
│   │   ├── pipeline.py             # 전체 RAG 파이프라인
│   │   ├── query/
│   │   │   └── query_processor.py  # 쿼리 재작성 + 의도 분류 (gpt-4o-mini)
│   │   ├── db/
│   │   │   ├── resolution_db.py    # 의결서 Chroma DB 구축 및 조회
│   │   │   └── scenario_db.py      # 엑셀 QA 로드 및 BM25 검색
│   │   ├── ingestion/
│   │   │   ├── embedder.py         # BGE-m3-ko 텍스트 임베딩 (CUDA, fp16)
│   │   │   └── excel_loader.py     # QA 엑셀 파일 로드 및 전처리
│   │   └── retrieval/
│   │       ├── hybrid_search.py    # Dense + BM25 하이브리드 검색 및 RRF 결합
│   │       ├── reranker.py         # Cross-Encoder 리랭킹 (CUDA, fp16, async)
│   │       └── filter.py           # GPT-4o-mini 기반 LLM 시맨틱 필터링
│   └── schemas/
│       ├── rag_output.py           # RAG 파이프라인 출력 스키마
│       └── report_output.py        # 에이전트 출력 스키마
│
├── data/
│   ├── raw/
│   │   ├── resolutions/            # 의결서 원본 데이터 (gitignore)
│   │   │                           # 파일 구조: {제목}_hybrid.json + {제목}_metadata.json
│   │   └── scenarios.xlsx          # 공정거래 QA 데이터셋 500개 (gitignore)
│   └── processed/
│       └── chroma_db/              # BGE-m3-ko 임베딩 벡터 DB 31,877개 청크 (gitignore)
│
├── models/                         # 로컬 모델 저장소 (gitignore)
│   ├── BGE-m3-ko/                  # 임베딩 모델
│   └── ko-reranker/                # 리랭킹 모델
│
├── scripts/
│   ├── build_db.py                 # 의결서 → Chroma DB 구축 (최초 1회)
│   ├── download_models.py          # 모델 다운로드 (최초 1회)
│   └── test_pipeline.py            # RAG 파이프라인 통합 테스트
│
├── .env
├── .gitignore
└── requirements.txt
```

---

## 동작 흐름

```
웹 (질문화면.html)
        ↓ POST /diagnose { user_query, situation_type }
FastAPI (routes.py)
        ↓
┌──────────────────────────────────────┐
│  1단계: RAG 파이프라인               │
│  ① 쿼리 재작성 (GPT-4o-mini)        │
│  ② Hybrid Search → Top 10           │
│     Dense(BGE-m3-ko) + BM25 + RRF   │
│  ③ Reranking (ko-reranker) → Top 10 │
│  ④ LLM Filter (GPT-4o-mini) → Top 5 │
│  ⑤ 시나리오 BM25 검색 → Top 3       │
└──────────────────────────────────────┘
        ↓ 의결서 청크 5건 + 시나리오 3건
┌──────────────────────────────────────┐
│  2단계: MCP 검색 (국가법령정보 API)  │
│  법령 / 판례 / 공정위 결정문         │
└──────────────────────────────────────┘
        ↓
┌──────────────────────────────────────┐
│  3단계: 4개 에이전트 병렬 분석       │
│  법령 해석 / 의결서 해석             │
│  판례 해석 / 사례 기반 해석          │
└──────────────────────────────────────┘
        ↓
┌──────────────────────────────────────┐
│  4단계: 종합 에이전트                │
│  위험도 판정 + 권고사항 생성         │
└──────────────────────────────────────┘
        ↓
웹 (결과화면.html) ← FinalReport (JSON)
```

---

## 사용 모델

| 역할 | 모델 |
|---|---|
| 임베딩 | `dragonkue/BGE-m3-ko` (CUDA, fp16) |
| 쿼리 재작성 + LLM 필터 + 에이전트 | `gpt-4o-mini` |
| 리랭킹 | `Dongjin-kr/ko-reranker` (Cross-Encoder, CUDA, fp16) |

---

## 최초 실행 설정 (최초 1회만 실행)

**1. 패키지 설치**
```cmd
pip install -r requirements.txt
pip install mcp
```

**2. 환경 변수 설정**

`.env` 파일에 아래 값 입력

```
OPENAI_API_KEY=sk-...
LAW_API_OC=your_id
```

**3. 모델 다운로드**
```cmd
python scripts/download_models.py
```

**4. DB 구축**
```cmd
python scripts/build_db.py
```

---

## 서버 실행

**백엔드 서버 실행** (`backend/` 폴더에서)

```cmd
cd backend
uvicorn main:app --reload
```

**프론트엔드 접속**

```
http://localhost:8000/질문화면.html
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

## situation_type 종류

| 영어 (HTML) | 한글 (에이전트) |
|---|---|
| `suspected` | `위반 의심 사항` |
| `in_progress` | `거래 진행 중` |
| `contract_before` | `계약 체결 전` |
| `regular_check` | `정기 점검` |

---

## 프롬프트 수정 방법

| 에이전트 | 파일 |
|---|---|
| 법령 해석 | `backend/agents/law_agent.py` |
| 의결서 해석 | `backend/agents/resolution_agent.py` |
| 판례 해석 | `backend/agents/precedent_agent.py` |
| 사례 기반 해석 | `backend/agents/case_agent.py` |
| 종합 분석 | `backend/agents/synthesis_agent.py` |

---

## RAGOutput JSON (서준원 파트 출력 예시)

`pipeline.run()` 실행 시 에이전트로 전달되는 데이터 구조예요.

```json
{
  "user_query": "자사상품 검색 상단에 올리면 문제되나요?",
  "situation_type": "suspected",
  "rewritten_query": "자사상품 검색 상단 노출의 법적 문제 여부",
  "resolution_docs": [
    {
      "doc_id": "DOC-6b3d...-CH-242",
      "content": "PB상품 등의 검색순위 상위 노출은...",
      "score": 0.664,
      "metadata": {
        "의결서제목": "쿠팡(주) 등의 불공정거래행위에 대한 건",
        "위반유형": "부당한 고객유인",
        "세부위반유형": "위계에 의한 고객유인",
        "조치유형": "과징금",
        "피심인기업명": "쿠팡(주)",
        "공개일자": "20241023",
        "section": "이유",
        "chunk_type": "text"
      }
    }
  ],
  "scenario_docs": [
    {
      "question": "...",
      "answer": "...",
      "legal_interpretation": "...",
      "evidence": "...",
      "situation_type": "suspected"
    }
  ]
}
```

네 가능해요.

---

**용현 작업 관련 내용**

**1. 서버 실행**
```cmd
cd backend
uvicorn main:app --reload
```

브라우저에서 `http://localhost:8000/질문화면.html` 접속

---

**2. 흐름**
```
질문화면.html에서 질문 입력 + 상황유형 선택 → 진단 시작 버튼
    ↓
AI 분석 자동 실행 (30초~1분 소요)
    ↓
결과화면.html로 자동 이동
    ↓
sessionStorage에서 결과 JSON 꺼내서 화면에 출력
```

---

**3. 결과 JSON 꺼내는 법**
```javascript
const result = JSON.parse(sessionStorage.getItem('diagnoseResult'));
```

---

**4. 주요 필드**
```javascript
result.risk_level           // "낮음/보통/높음/매우 높음"
result.overall_confidence   // 신뢰도 점수 (0~100)
result.synthesis            // 종합 분석 텍스트
result.recommendations      // 권고사항 배열 ["...", "..."]
result.caveats              // 주의사항

result.agent_reports        // 에이전트별 분석 배열
  └ .agent_name             // 에이전트 이름
  └ .analysis               // 분석 내용
  └ .confidence_score       // 신뢰도 (0~100)
  └ .key_findings           // 핵심 발견 배열 ["...", "..."]
```

---

**5. 할 일**
`결과화면(예시).html` 디자인에 위 필드들 연결해서 동적으로 출력하면 됨.

현재 `결과화면_더미.html`이 JSON 그대로 출력하는 버전이니까 참고용으로 쓰면 됨.
