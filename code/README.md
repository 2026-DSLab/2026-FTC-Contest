# 공정거래 법률 분석 파이프라인

**담당: 이승건**  
국가법령정보 공동활용 API(MCP)를 활용한 멀티에이전트 법률 분석 모듈입니다.  
전체 시스템 중 이 모듈이 담당하는 범위: **쿼리 재작성 → 외부 법령 검색(MCP) → 다면적 법리 해석 → 최종 레포트 생성**

> RAG(Internal Retrieval) 파트는 이 모듈에서 제외되어 있습니다. 다른 팀원이 구축한 RAG와 나중에 연결할 수 있도록 `ExternalEvidence` 데이터 모델에 인터페이스가 마련되어 있습니다.

---

## 목차

1. [디렉토리 구조](#1-디렉토리-구조)
2. [전체 데이터 흐름](#2-전체-데이터-흐름)
3. [환경 설정](#3-환경-설정)
4. [파일별 상세 설명](#4-파일별-상세-설명)
   - [models.py](#41-modelspy--공통-데이터-모델)
   - [query_rewriter.py](#42-query_rewriterpy--step-1-쿼리-재작성--의도-분류)
   - [mcp_retriever.py](#43-mcp_retrieverpy--step-2-외부-법령-검색)
   - [agents/base_agent.py](#44-agentsbase_agentpy--에이전트-공통-기반)
   - [agents/law_agent.py](#45-agentslaw_agentpy--법령-해석-에이전트)
   - [agents/resolution_agent.py](#46-agentsresolution_agentpy--의결서-해석-에이전트)
   - [agents/precedent_agent.py](#47-agentsprecedent_agentpy--판례결정문-해석-에이전트)
   - [agents/case_agent.py](#48-agentscase_agentpy--사례-기반-해석-에이전트)
   - [agents/synthesis_agent.py](#49-agentssynthesis_agentpy--종합-분석-에이전트)
   - [pipeline.py](#410-pipelinepy--전체-파이프라인-오케스트레이터)
   - [main.py](#411-mainpy--cli-진입점)
5. [실행 방법](#5-실행-방법)
6. [자주 수정하는 포인트](#6-자주-수정하는-포인트)
7. [웹 배포 시 연동 방법](#7-웹-배포-시-연동-방법)

---

## 1. 디렉토리 구조

```
2026-FTC-Contest/
│
├── law_server.py              # [기존] MCP 서버 — 국가법령정보 API 래핑
├── .env                       # API 키 (git에 올리지 말 것)
├── .env.example               # .env 양식
├── requirements.txt           # Python 패키지 목록
│
└── code/                      # ← 이 모듈의 루트
    ├── __init__.py            # LegalAnalysisPipeline 등 외부 공개 심볼
    ├── models.py              # 모든 데이터 모델 (Pydantic)
    ├── query_rewriter.py      # Step 1: 쿼리 재작성 & 의도 분류
    ├── mcp_retriever.py       # Step 2: MCP로 법령/판례/결정문 검색
    ├── pipeline.py            # 전체 흐름 조율 (오케스트레이터)
    ├── main.py                # CLI 진입점
    └── agents/
        ├── __init__.py        # 에이전트 클래스 일괄 공개
        ├── base_agent.py      # 에이전트 공통 추상 기반 클래스
        ├── law_agent.py       # 법령 해석 에이전트
        ├── resolution_agent.py # 의결서 해석 에이전트
        ├── precedent_agent.py  # 판례·결정문 해석 에이전트
        ├── case_agent.py      # 사례 기반 해석 에이전트
        └── synthesis_agent.py # 종합 분석 에이전트 (최종 레포트)
```

---

## 2. 전체 데이터 흐름

```
사용자 질문 (str)
    │
    ▼
[Step 1] query_rewriter.py
    QueryRewriter.rewrite()
    → RewrittenQuery
      ├── original          원본 질문
      ├── rewritten         법률 전문 용어로 재작성된 쿼리
      ├── intent
      │   ├── category      의도 카테고리 (7종)
      │   ├── sub_intent    구체적 법률 쟁점 설명
      │   └── legal_issues  쟁점 목록 (3~5개)
      └── search_keywords   MCP 검색용 키워드 (3~7개)
    │
    ▼
[Step 2] mcp_retriever.py
    MCPRetriever.retrieve_sync()
    → law_server.py (subprocess / stdio MCP 프로토콜)
      ├── search_law → get_law_content       법령 본문
      ├── search_precedent → get_precedent_content  판례 전문
      └── search_ftc_decision → get_ftc_decision_content  공정위 결정문
    → ExternalEvidence
      ├── laws[]            LawDocument 목록
      ├── precedents[]      LawDocument 목록
      └── ftc_decisions[]   LawDocument 목록
    │
    ▼
[Step 3] agents/ (4개 에이전트, 기본 병렬 실행)
    ├── LawAgent.analyze()        → AgentReport (법령 해석)
    ├── ResolutionAgent.analyze() → AgentReport (의결서 해석)
    ├── PrecedentAgent.analyze()  → AgentReport (판례·결정문 해석)
    └── CaseAgent.analyze()       → AgentReport (사례 기반 해석)
    각 AgentReport:
      ├── analysis          상세 분석 (마크다운)
      ├── confidence_score  신뢰도 0~100
      ├── key_findings      핵심 발견 목록
      └── limitations       분석 한계 (선택)
    │
    ▼
[Step 4] agents/synthesis_agent.py
    SynthesisAgent.synthesize()
    → FinalReport
      ├── synthesis         종합 분석 (마크다운)
      ├── overall_confidence 종합 신뢰도 0~100
      ├── risk_level        낮음/보통/높음/매우 높음
      ├── recommendations   권고사항 목록
      ├── caveats           면책·한계 사항
      └── agent_reports[]   위 4개 보고서 포함
```

---

## 3. 환경 설정

### 패키지 설치

```bash
pip install -r requirements.txt
```

`requirements.txt` 내용:
```
anthropic>=0.40.0      # Claude API SDK
mcp>=1.0.0             # MCP 클라이언트/서버 라이브러리
pydantic>=2.0.0        # 데이터 모델 검증
httpx>=0.27.0          # 비동기 HTTP (law_server.py가 사용)
python-dotenv>=1.0.0   # .env 파일 로드
```

### .env 파일 설정

프로젝트 루트에 `.env` 파일 생성:

```env
ANTHROPIC_API_KEY=sk-ant-...   # Anthropic Console에서 발급
LAW_API_OC=sgrhee3             # 국가법령정보 OC ID (기본값 이미 설정됨)
```

`.env`는 절대 git에 올리지 말 것. `.env.example`이 양식 역할을 합니다.

---

## 4. 파일별 상세 설명

### 4.1 `models.py` — 공통 데이터 모델

모든 파일에서 import하는 Pydantic 데이터 모델 정의 파일입니다.  
파이프라인 각 단계의 입출력 타입이 여기에 정의되어 있습니다.

#### 클래스 목록

| 클래스 | 역할 | 주요 필드 |
|--------|------|-----------|
| `IntentCategory` | 의도 분류 enum (7종) | `UNFAIR_TRADE`, `MARKET_DOMINANT`, `MERGER`, `CARTEL`, `CONSUMER_PROTECTION`, `CONTRACT`, `OTHER` |
| `QueryIntent` | 분류된 의도 | `category`, `sub_intent`, `legal_issues[]` |
| `RewrittenQuery` | Step 1 출력 | `original`, `rewritten`, `intent`, `search_keywords[]` |
| `LawDocument` | 수집된 문서 1건 | `doc_type` ("law"/"precedent"/"ftc_decision"), `title`, `content`, `source_id` |
| `ExternalEvidence` | Step 2 출력 (수집 문서 묶음) | `laws[]`, `precedents[]`, `ftc_decisions[]` |
| `AgentReport` | 개별 에이전트 보고서 | `agent_type`, `agent_name`, `analysis`, `confidence_score` (0~100), `key_findings[]`, `limitations` |
| `FinalReport` | 최종 출력 | `synthesis`, `overall_confidence`, `risk_level`, `recommendations[]`, `agent_reports[]` |

#### 수정 포인트

- **의도 카테고리 추가/변경**: `IntentCategory` enum 값 수정 후 `query_rewriter.py`의 `SYSTEM_PROMPT` 카테고리 설명도 함께 수정
- **리스크 레벨 변경**: `FinalReport.risk_level`은 현재 문자열 타입 — `synthesis_agent.py`의 `_SYNTHESIS_TOOL` enum에서 제어

---

### 4.2 `query_rewriter.py` — Step 1: 쿼리 재작성 & 의도 분류

사용자의 구어체 질문을 법률 전문 쿼리로 바꾸고 의도를 분류합니다.

#### 동작 방식

Claude에게 `output_rewritten_query` 도구를 **강제 호출**(`tool_choice: "tool"`)시켜  
구조화된 JSON 응답을 보장합니다.

```python
# 사용 예시
from code.query_rewriter import QueryRewriter
import anthropic

client = anthropic.Anthropic()
rewriter = QueryRewriter(client)
result = rewriter.rewrite("A사가 대리점한테 경쟁사 제품 팔지 말라고 하는데 위법인가요?")
# result.rewritten → "독점규제 및 공정거래에 관한 법률 제23조 불공정거래행위 중..."
# result.intent.category → IntentCategory.UNFAIR_TRADE
# result.search_keywords → ["배타적 거래", "거래상 지위 남용", ...]
```

#### 수정 포인트 ★

`query_rewriter.py` 상단의 `SYSTEM_PROMPT` 변수를 수정하면 됩니다.

```python
# ──────────────────────────────────────────────
# 프롬프트 (수정 포인트 ▼)
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """당신은 공정거래 및 경쟁법 전문 법률 AI 어시스턴트입니다.
...
"""
```

`REWRITE_TOOL`의 `input_schema`를 수정하면 출력 필드 구조를 바꿀 수 있습니다.  
단, `models.py`의 `RewrittenQuery`, `QueryIntent` 필드와 일치해야 합니다.

---

### 4.3 `mcp_retriever.py` — Step 2: 외부 법령 검색

`law_server.py`를 **subprocess로 실행**하여 stdio MCP 프로토콜로 통신합니다.  
Claude를 거치지 않고 직접 API를 호출하는 유일한 단계입니다.

#### 동작 방식

```
MCPRetriever.retrieve_sync(keywords)
  └─ asyncio로 비동기 실행
       └─ MCP ClientSession
            ├─ search_law("키워드") → 검색 결과 XML
            │    └─ get_law_content(mst) → 법령 본문 XML  (상위 3건)
            ├─ search_precedent("키워드") → 검색 결과 XML
            │    └─ get_precedent_content(id) → 판례 전문 XML
            └─ search_ftc_decision("키워드") → 검색 결과 XML
                 └─ get_ftc_decision_content(id) → 결정문 전문 XML
```

`law_server.py`가 루트에 있어야 합니다. 경로는 자동 계산됩니다:

```python
LAW_SERVER_PATH = Path(__file__).parent.parent / "law_server.py"
# code/ 기준으로 ../law_server.py
```

#### 수정 포인트

파일 상단 상수 두 개로 검색량을 조절합니다:

```python
SEARCH_DISPLAY = 5    # 각 카테고리에서 검색할 결과 개수
MAX_DETAIL_FETCH = 3  # 본문까지 가져올 최대 문서 수 (API 호출량 영향)
```

`MCPRetriever` 생성 시 인자로도 전달 가능합니다:
```python
retriever = MCPRetriever(display=10, max_detail=5)
```

---

### 4.4 `agents/base_agent.py` — 에이전트 공통 기반

4개 해석 에이전트가 모두 상속하는 추상 클래스입니다.  
직접 수정할 일은 거의 없지만, 구조를 이해하는 데 중요합니다.

#### 핵심 로직

모든 에이전트는 `REPORT_TOOL`을 사용해 Claude가 구조화된 보고서를 반드시 출력하도록 강제합니다:

```python
tool_choice={"type": "tool", "name": "output_report"}
```

Claude에게 전달되는 user message 구조:
```
## 분석 대상 질문
{query.rewritten}

## 법률 쟁점
- {쟁점1}
- {쟁점2}
...

## 외부 자료
## 관련 법령
### {법령명}
{법령 본문 (최대 3000자)}

## 관련 판례
...
```

#### 문서 길이 제한

각 문서는 **3000자**로 잘라서 전달합니다 (`base_agent.py` 내 `_format_evidence` 함수).  
컨텍스트가 너무 길어지는 것을 막기 위해서입니다. 필요하면 이 값을 조정하세요:

```python
# base_agent.py의 _format_evidence 함수
parts.append(doc.content[:3000])  # ← 이 숫자를 조정
```

---

### 4.5 `agents/law_agent.py` — 법령 해석 에이전트

**관점**: 법령 조문 → 구성요건 충족 여부 → 위반 판단 → 제재 규정

- `agent_type = "law"`
- `agent_name = "법령 해석 에이전트"`

#### 수정 포인트 ★

파일 상단 `_SYSTEM_PROMPT` 변수만 수정하면 됩니다:

```python
# ──────────────────────────────────────────────
# 프롬프트 수정 포인트 ▼
# ──────────────────────────────────────────────
_SYSTEM_PROMPT = """당신은 공정거래법 및 관련 법령 조문 해석 전문가입니다.
...
"""
```

Confidence Score 기준도 프롬프트 안에 정의되어 있어 함께 수정할 수 있습니다.

---

### 4.6 `agents/resolution_agent.py` — 의결서 해석 에이전트

**관점**: 공정위 의결 사례 비교 → FTC 판단 기준 → 예상 제재 수위 → 절차적 고려사항

- `agent_type = "resolution"`
- `agent_name = "의결서 해석 에이전트"`

수정 방법은 [4.5](#45-agentslaw_agentpy--법령-해석-에이전트)와 동일합니다.

---

### 4.7 `agents/precedent_agent.py` — 판례·결정문 해석 에이전트

**관점**: 판례 법리 추출 → 법원 판단 기준 → 최근 판례 경향 → 승소 가능성

- `agent_type = "precedent"`
- `agent_name = "판례·결정문 해석 에이전트"`

수정 방법은 [4.5](#45-agentslaw_agentpy--법령-해석-에이전트)와 동일합니다.

---

### 4.8 `agents/case_agent.py` — 사례 기반 해석 에이전트

**관점**: 사실관계 유사성 분석 → 차별화 요소 → 결과 예측 → 전략적 시사점

- `agent_type = "case"`
- `agent_name = "사례 기반 해석 에이전트"`

수정 방법은 [4.5](#45-agentslaw_agentpy--법령-해석-에이전트)와 동일합니다.

---

### 4.9 `agents/synthesis_agent.py` — 종합 분석 에이전트

4개 에이전트의 `AgentReport`를 받아 **Confidence Score를 가중치**로 활용해 최종 `FinalReport`를 생성합니다.

#### Claude에게 전달되는 정보

각 에이전트 보고서는 아래 형식으로 포맷되어 전달됩니다:

```
## 법령 해석 에이전트 (신뢰도: 75/100 [███████░░░])

{analysis 내용}

**핵심 발견:**
- 발견1
- 발견2

**한계:** ...
```

#### 수정 포인트 ★

`_SYSTEM_PROMPT` 수정으로 종합 방식을 조정할 수 있습니다.  
`_SYNTHESIS_TOOL`의 `risk_level` enum을 수정하면 리스크 레벨 기준도 바꿀 수 있습니다:

```python
"risk_level": {
    "type": "string",
    "enum": ["낮음", "보통", "높음", "매우 높음"],  # ← 여기 수정
    ...
},
```

`max_tokens=4096`으로 설정되어 있어 다른 에이전트(2048)보다 긴 응답이 가능합니다.

---

### 4.10 `pipeline.py` — 전체 파이프라인 오케스트레이터

4단계를 순서대로 실행하며, 각 단계를 **개별적으로 호출**할 수도 있습니다.

#### 전체 실행

```python
from code.pipeline import LegalAnalysisPipeline

pipeline = LegalAnalysisPipeline()
report = pipeline.run("질문 내용", verbose=True)
```

#### 단계별 개별 실행 (디버깅·테스트 용도)

```python
pipeline = LegalAnalysisPipeline()

# 1단계만 실행
rewritten = pipeline.step1_rewrite("질문")
print(rewritten.rewritten)

# 2단계만 실행 (1단계 결과 필요)
evidence = pipeline.step2_retrieve(rewritten)
print(len(evidence.laws))

# 3단계만 실행 (1~2단계 결과 필요)
reports = pipeline.step3_analyze(rewritten, evidence)

# 4단계만 실행 (1, 3단계 결과 필요)
final = pipeline.step4_synthesize(rewritten, reports)
```

#### 생성자 파라미터

```python
LegalAnalysisPipeline(
    anthropic_api_key=None,     # None이면 환경변수 ANTHROPIC_API_KEY 사용
    model="claude-sonnet-4-6",  # 사용할 Claude 모델
    parallel_agents=True,       # True: 4개 에이전트 병렬 / False: 순차 실행
)
```

#### 병렬 실행 구조

`parallel_agents=True`(기본값)일 때 `ThreadPoolExecutor`로 4개 에이전트를 동시에 실행합니다.  
API 비용은 동일하지만 응답 시간이 단축됩니다. 디버깅 시에는 `parallel_agents=False`로 전환하면 좋습니다.

---

### 4.11 `main.py` — CLI 진입점

터미널에서 바로 실행 가능한 인터페이스입니다.

#### 사용법

```bash
# 기본 실행
python -m code.main "A사가 하도급 업체에 단가를 일방적으로 인하했습니다. 위법인가요?"

# 병렬 끄기 (디버깅)
python -m code.main "질문" --no-parallel

# 결과 JSON 저장
python -m code.main "질문" --output result.json

# 다른 모델 사용
python -m code.main "질문" --model claude-opus-4-8

# 인자 없이 실행 시 대화형 입력
python -m code.main
```

#### 저장 JSON 형식

`--output` 옵션 사용 시 `FinalReport` Pydantic 모델이 그대로 JSON으로 직렬화됩니다:

```json
{
  "original_query": "...",
  "rewritten_query": "...",
  "intent_category": "불공정거래행위",
  "legal_issues": ["...", "..."],
  "agent_reports": [
    {
      "agent_type": "law",
      "agent_name": "법령 해석 에이전트",
      "analysis": "...",
      "confidence_score": 78,
      "key_findings": ["...", "..."],
      "limitations": "..."
    },
    ...
  ],
  "synthesis": "...",
  "overall_confidence": 72,
  "risk_level": "높음",
  "recommendations": ["...", "..."],
  "caveats": "..."
}
```

---

## 5. 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. .env 설정
copy .env.example .env
# .env 파일을 열어 ANTHROPIC_API_KEY 입력

# 3. 프로젝트 루트에서 실행 (code는 패키지이므로 루트에서 실행해야 함)
cd C:\Users\user\Documents\2026-FTC-Contest
python -m code.main "질문 입력"
```

---

## 6. 자주 수정하는 포인트

### 프롬프트 수정

각 에이전트의 분석 관점이나 지시사항을 바꾸려면 해당 파일 상단의 `_SYSTEM_PROMPT`만 수정하면 됩니다.

| 수정 대상 | 파일 | 변수명 |
|-----------|------|--------|
| 쿼리 재작성 방식 / 의도 분류 기준 | `query_rewriter.py` | `SYSTEM_PROMPT` |
| 법령 해석 관점 / 신뢰도 기준 | `agents/law_agent.py` | `_SYSTEM_PROMPT` |
| 의결서 해석 관점 / 신뢰도 기준 | `agents/resolution_agent.py` | `_SYSTEM_PROMPT` |
| 판례 해석 관점 / 신뢰도 기준 | `agents/precedent_agent.py` | `_SYSTEM_PROMPT` |
| 사례 비교 관점 / 신뢰도 기준 | `agents/case_agent.py` | `_SYSTEM_PROMPT` |
| 종합 방식 / 리스크 판단 기준 | `agents/synthesis_agent.py` | `_SYSTEM_PROMPT` |

### 검색량 조정

```python
# mcp_retriever.py 상단
SEARCH_DISPLAY = 5    # 검색 결과 수 → 늘리면 더 많은 후보 확인
MAX_DETAIL_FETCH = 3  # 본문 수집 수 → 늘리면 더 많은 내용 전달 (API 호출 증가)
```

### 모델 변경

```python
# 실행 시 인자로 지정
pipeline = LegalAnalysisPipeline(model="claude-opus-4-8")

# 또는 CLI
python -m code.main "질문" --model claude-opus-4-8
```

---

## 7. 웹 배포 시 연동 방법

FastAPI 등 웹 프레임워크와 연동할 때는 `LegalAnalysisPipeline`을 import해서 사용하면 됩니다.

```python
from fastapi import FastAPI
from code.pipeline import LegalAnalysisPipeline
from code.models import FinalReport

app = FastAPI()
pipeline = LegalAnalysisPipeline()  # 앱 시작 시 1회 초기화

@app.post("/analyze", response_model=FinalReport)
def analyze(query: str):
    return pipeline.run(query)
```

### RAG 연동 (나중에 다른 팀원 파트와 합칠 때)

현재 `ExternalEvidence`에는 MCP로 수집한 문서만 들어갑니다.  
RAG에서 가져온 문서를 추가하려면 `pipeline.py`의 `step2_retrieve` 이후에 다음처럼 삽입하면 됩니다:

```python
def step2_retrieve(self, query: RewrittenQuery) -> ExternalEvidence:
    evidence = self.mcp_retriever.retrieve_sync(query.search_keywords)
    
    # ↓ RAG 연동 포인트
    rag_docs = rag_module.search(query.rewritten)  # 팀원 RAG 모듈
    for doc in rag_docs:
        evidence.laws.append(LawDocument(
            doc_type="law",
            title=doc.title,
            content=doc.content
        ))
    
    return evidence
```
