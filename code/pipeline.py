"""
전체 파이프라인 오케스트레이터
User Query + SituationType
  → RAGPipeline (쿼리 재작성 + 의결서/시나리오 검색)
  → MCPRetriever (법령/판례/결정문 검색)
  → 증거 통합
  → 4개 에이전트 병렬 분석
  → 종합 분석
  → FinalReport
"""
from __future__ import annotations

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

# backend/ 디렉토리를 sys.path에 추가 (RAG 모듈 import를 위해)
_BACKEND_DIR = Path(__file__).parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from rag.pipeline import RAGPipeline  # noqa: E402

from .agents import CaseAgent, LawAgent, PrecedentAgent, ResolutionAgent, SynthesisAgent
from .mcp_retriever import MCPRetriever
from .models import (
    AgentReport,
    ExternalEvidence,
    FinalReport,
    LawDocument,
    ScenarioDoc,
    SituationType,
)


def _rag_to_evidence(rag_output) -> ExternalEvidence:
    """RAGOutput → ExternalEvidence 변환"""
    resolution_chunks = [
        LawDocument(
            doc_type="resolution_chunk",
            title=doc.metadata.get("제목", "") or doc.metadata.get("title", ""),
            content=doc.content,
            source_id=doc.doc_id,
            score=doc.score,
        )
        for doc in rag_output.resolution_docs
    ]
    scenario_docs = [
        ScenarioDoc(
            question=doc.question,
            answer=doc.answer,
            legal_interpretation=doc.legal_interpretation,
            evidence=doc.evidence,
            situation_type=doc.situation_type,
        )
        for doc in rag_output.scenario_docs
    ]
    return ExternalEvidence(
        resolution_chunks=resolution_chunks,
        scenario_docs=scenario_docs,
    )


def _merge_evidence(rag_evidence: ExternalEvidence, mcp_evidence: ExternalEvidence) -> ExternalEvidence:
    """RAG 결과 + MCP 결과 통합"""
    return ExternalEvidence(
        laws=mcp_evidence.laws,
        precedents=mcp_evidence.precedents,
        ftc_decisions=mcp_evidence.ftc_decisions,
        resolution_chunks=rag_evidence.resolution_chunks,
        scenario_docs=rag_evidence.scenario_docs,
    )


class LegalAnalysisPipeline:
    """법률 분석 파이프라인 전체를 관리합니다."""

    def __init__(
        self,
        openai_api_key: str | None = None,
        model: str = "gpt-4o-mini",
        parallel_agents: bool = True,
        rag_db_path: str = "data/processed/chroma_db",
        rag_excel_path: str = "data/raw/scenarios.xlsx",
    ):
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.parallel_agents = parallel_agents

        self.rag_pipeline = RAGPipeline(
            db_path=rag_db_path,
            excel_path=rag_excel_path,
        )
        self.mcp_retriever = MCPRetriever()
        self.agents = [
            LawAgent(self.client, model),
            ResolutionAgent(self.client, model),
            PrecedentAgent(self.client, model),
            CaseAgent(self.client, model),
        ]
        self.synthesis_agent = SynthesisAgent(self.client, model)

    # ── 단계별 메서드 (개별 호출 가능) ────────────────────

    def step1_rag(self, user_query: str, situation_type: str):
        """Step 1: RAGPipeline 실행 (쿼리 재작성 + 의결서/시나리오 검색)"""
        return asyncio.run(self.rag_pipeline.run(user_query, situation_type))

    def step2_mcp(self, rewritten_query: str) -> ExternalEvidence:
        """Step 2: MCP로 법령·판례·결정문 검색 (재작성 쿼리를 키워드로 활용)"""
        keywords = rewritten_query.split()[:7]
        return self.mcp_retriever.retrieve_sync(keywords)

    def step3_analyze(
        self,
        original_query: str,
        rewritten_query: str,
        evidence: ExternalEvidence,
    ) -> list[AgentReport]:
        """Step 3: 4개 에이전트 병렬/순차 분석"""
        if self.parallel_agents:
            return self._run_agents_parallel(original_query, rewritten_query, evidence)
        return self._run_agents_sequential(original_query, rewritten_query, evidence)

    def step4_synthesize(
        self,
        original_query: str,
        rewritten_query: str,
        situation_type: str,
        reports: list[AgentReport],
    ) -> FinalReport:
        """Step 4: 종합 분석 에이전트로 최종 레포트 생성"""
        return self.synthesis_agent.synthesize(
            original_query, rewritten_query, situation_type, reports
        )

    # ── 전체 실행 ──────────────────────────────────────────

    def run(
        self,
        user_query: str,
        situation_type: str | SituationType = SituationType.SUSPECTED,
        verbose: bool = False,
    ) -> FinalReport:
        """전체 파이프라인을 순서대로 실행합니다."""
        if isinstance(situation_type, SituationType):
            situation_type_key = situation_type.to_rag_key()
            situation_type_label = situation_type.value
        else:
            situation_type_key = situation_type
            situation_type_label = situation_type

        if verbose:
            print(f"[1/4] RAG 파이프라인 실행 중 (상황유형: {situation_type_label})...")
        rag_output = self.step1_rag(user_query, situation_type_key)
        if verbose:
            print(f"  → 재작성: {rag_output.rewritten_query}")
            print(
                f"  → 의결서 청크 {len(rag_output.resolution_docs)}건 / "
                f"시나리오 {len(rag_output.scenario_docs)}건 수집"
            )

        if verbose:
            print(f"[2/4] MCP 법령·판례 검색 중...")
        mcp_evidence = self.step2_mcp(rag_output.rewritten_query)
        if verbose:
            print(
                f"  → 법령 {len(mcp_evidence.laws)}건 / 판례 {len(mcp_evidence.precedents)}건 / "
                f"공정위 결정문 {len(mcp_evidence.ftc_decisions)}건 수집"
            )

        rag_evidence = _rag_to_evidence(rag_output)
        combined = _merge_evidence(rag_evidence, mcp_evidence)

        if verbose:
            print(f"[3/4] 다면적 법리 해석 에이전트 실행 중{'(병렬)' if self.parallel_agents else '(순차)'}...")
        reports = self.step3_analyze(user_query, rag_output.rewritten_query, combined)
        if verbose:
            for r in reports:
                print(f"  → [{r.agent_name}] 신뢰도: {r.confidence_score}/100")

        if verbose:
            print(f"[4/4] 최종 종합 보고서 생성 중...")
        final = self.step4_synthesize(
            user_query, rag_output.rewritten_query, situation_type_label, reports
        )
        if verbose:
            print(f"  → 종합 신뢰도: {final.overall_confidence}/100 | 리스크: {final.risk_level}")

        return final

    # ── 내부 헬퍼 ─────────────────────────────────────────

    def _run_agents_parallel(
        self,
        original_query: str,
        rewritten_query: str,
        evidence: ExternalEvidence,
    ) -> list[AgentReport]:
        reports: list[AgentReport] = [None] * len(self.agents)  # type: ignore
        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            futures = {
                executor.submit(agent.analyze, original_query, rewritten_query, evidence): idx
                for idx, agent in enumerate(self.agents)
            }
            for future in as_completed(futures):
                idx = futures[future]
                reports[idx] = future.result()
        return reports

    def _run_agents_sequential(
        self,
        original_query: str,
        rewritten_query: str,
        evidence: ExternalEvidence,
    ) -> list[AgentReport]:
        return [agent.analyze(original_query, rewritten_query, evidence) for agent in self.agents]
