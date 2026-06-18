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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_CHROMA_PATH = os.environ.get(
    "CHROMA_DB_PATH",
    str(Path.home() / "ftc_chroma_db"),
)

from rag.pipeline import RAGPipeline
from agents import CaseAgent, LawAgent, PrecedentAgent, ResolutionAgent, SynthesisAgent
from mcp_retriever import MCPRetriever
from models import (
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
    """RAG 결과 + MCP 결과 통합 (source_id 기준 중복 제거)"""
    def _dedup(docs: list) -> list:
        seen: set = set()
        result = []
        for doc in docs:
            key = doc.source_id or doc.title or doc.content[:80]
            if key not in seen:
                seen.add(key)
                result.append(doc)
        return result

    return ExternalEvidence(
        laws=_dedup(mcp_evidence.laws),
        precedents=_dedup(mcp_evidence.precedents),
        ftc_decisions=_dedup(mcp_evidence.ftc_decisions),
        resolution_chunks=_dedup(rag_evidence.resolution_chunks),
        scenario_docs=rag_evidence.scenario_docs,
    )


class LegalAnalysisPipeline:
    """법률 분석 파이프라인 전체를 관리합니다."""

    def __init__(
        self,
        openai_api_key: str | None = None,
        model: str = "gpt-4o-mini",
        parallel_agents: bool = True,
        rag_db_path: str = _DEFAULT_CHROMA_PATH,
        rag_excel_path: str = str(_PROJECT_ROOT / "data/raw/scenarios.xlsx"),
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

    def step2_mcp(self, mcp_law_query: str, mcp_prec_query: str) -> ExternalEvidence:
        """Step 2: MCP로 법령·판례 검색 (law/prec 각각 최적화된 쿼리 사용)"""
        return self.mcp_retriever.retrieve_sync(mcp_law_query, mcp_prec_query)

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
        law_docs=None,
        resolution_chunks=None,
    ) -> FinalReport:
        """Step 4: 종합 분석 에이전트로 최종 레포트 생성"""
        return self.synthesis_agent.synthesize(
            original_query, rewritten_query, situation_type, reports, law_docs, resolution_chunks
        )

    # ── 전체 실행 ──────────────────────────────────────────

    def run(
        self,
        user_query: str,
        situation_type: str | SituationType = SituationType.SUSPECTED,
        verbose: bool = False,
    ) -> FinalReport:
        """전체 파이프라인을 순서대로 실행합니다."""
        final, _ = self.run_traced(user_query, situation_type, verbose)
        return final

    def run_traced(
        self,
        user_query: str,
        situation_type: str | SituationType = SituationType.SUSPECTED,
        verbose: bool = False,
    ) -> tuple[FinalReport, dict]:
        """전체 파이프라인을 실행하고 (FinalReport, pipeline_trace) 튜플을 반환합니다.
        pipeline_trace에는 각 단계의 중간 결과가 담겨 있습니다 (4.3절 데이터 활용결과용).
        """
        if isinstance(situation_type, SituationType):
            situation_type_key = situation_type.to_rag_key()
            situation_type_label = situation_type.value
        else:
            situation_type_key = situation_type
            situation_type_label = situation_type

        t_total = time.time()

        if verbose:
            print(f"\n{'='*60}")
            print(f"[1/4] 쿼리 재작성 중 (상황유형: {situation_type_label})...")
        t0 = time.time()

        # 1단계: 쿼리 재작성 (RAG, MCP 모두 이 결과가 필요)
        processed = asyncio.run(
            self.rag_pipeline.process_query_only(user_query)
        )
        rewritten = processed["rewritten_query"]
        law_q = processed.get("mcp_law_query") or "독점규제 공정거래"
        prec_q = processed.get("mcp_prec_query") or rewritten

        if verbose:
            print(f"  → 재작성: {rewritten}")
            print(f"  ⏱ 쿼리 재작성 소요: {time.time() - t0:.1f}초")
            print(f"[2/4] RAG 검색 + MCP 법령·판례 검색 병렬 실행 중...")
        t1 = time.time()

        # 2단계: RAG 검색 본체 + MCP를 진정한 병렬로 실행
        def _run_rag_search():
            _t = time.time()
            result = asyncio.run(
                self.rag_pipeline.run_search_only(user_query, situation_type_key, processed)
            )
            if verbose:
                print(f"    [RAG 검색 완료] ⏱ {time.time() - _t:.1f}초")
            return result

        def _run_mcp():
            _t = time.time()
            result = self.mcp_retriever.retrieve_sync(law_q, prec_q)
            if verbose:
                print(f"    [MCP 검색 완료] ⏱ {time.time() - _t:.1f}초")
            return result

        with ThreadPoolExecutor(max_workers=2) as executor:
            rag_future = executor.submit(_run_rag_search)
            mcp_future = executor.submit(_run_mcp)
            rag_output = rag_future.result()
            mcp_evidence = mcp_future.result()

        if verbose:
            print(
                f"  → RAG: 하이브리드 {len(rag_output.hybrid_search_raw)}건 → "
                f"리랭킹 {len(rag_output.reranked_raw)}건 → "
                f"필터 {len(rag_output.filtered_raw)}건 / "
                f"시나리오 {len(rag_output.scenario_docs)}건"
            )
            print(
                f"  → MCP: 법령 {len(mcp_evidence.laws)}건 / 판례 {len(mcp_evidence.precedents)}건 / "
                f"결정문 {len(mcp_evidence.ftc_decisions)}건"
            )
            print(f"  ⏱ RAG+MCP 병렬 소요: {time.time() - t1:.1f}초")

        rag_evidence = _rag_to_evidence(rag_output)
        combined = _merge_evidence(rag_evidence, mcp_evidence)

        if verbose:
            print(f"[3/4] 다면적 법리 해석 에이전트 실행 중{'(병렬)' if self.parallel_agents else '(순차)'}...")
        t2 = time.time()
        reports = self.step3_analyze(user_query, rag_output.rewritten_query, combined)
        if verbose:
            for r in reports:
                print(f"  → [{r.agent_name}] 신뢰도: {r.confidence_score}/100")
            print(f"  ⏱ 4개 에이전트 병렬 분석 소요: {time.time() - t2:.1f}초")

        if verbose:
            print(f"[4/4] 최종 종합 보고서 생성 중...")
        t3 = time.time()
        final = self.step4_synthesize(
            user_query, rag_output.rewritten_query, situation_type_label, reports,
            combined.laws, combined.resolution_chunks
        )
        if verbose:
            print(f"  → 종합 신뢰도: {final.overall_confidence}/100 | 리스크: {final.risk_level}")
            print(f"  ⏱ 종합 보고서 생성 소요: {time.time() - t3:.1f}초")
            print(f"{'='*60}")
            print(f"⏱ 전체 파이프라인 소요: {time.time() - t_total:.1f}초")
            print(f"{'='*60}\n")

        pipeline_trace = {
            "rag": {
                "query_intent": rag_output.query_intent,
                "mcp_law_query": rag_output.mcp_law_query,
                "mcp_prec_query": rag_output.mcp_prec_query,
                "hybrid_search_results": [doc.model_dump() for doc in rag_output.hybrid_search_raw],
                "reranked_results": [doc.model_dump() for doc in rag_output.reranked_raw],
                "filtered_results": [doc.model_dump() for doc in rag_output.filtered_raw],
                "scenario_results": [doc.model_dump() for doc in rag_output.scenario_docs],
            },
            "mcp": {
                "laws": [doc.model_dump() for doc in mcp_evidence.laws],
                "precedents": [doc.model_dump() for doc in mcp_evidence.precedents],
                "ftc_decisions": [doc.model_dump() for doc in mcp_evidence.ftc_decisions],
            },
        }

        return final, pipeline_trace

    async def run_stream(
        self,
        user_query: str,
        situation_type: str | SituationType = SituationType.SUSPECTED,
    ):
        """SSE (Server-Sent Events)를 위한 비동기 상태 스트리밍 파이프라인"""
        import json

        if isinstance(situation_type, SituationType):
            situation_type_key = situation_type.to_rag_key()
            situation_type_label = situation_type.value
        else:
            situation_type_key = situation_type
            situation_type_label = situation_type

        step1_message = "1/4 쿼리 재작성 중..."
        yield json.dumps({"status": "processing", "step": 1, "message": step1_message}) + "\n"

        query_task = asyncio.create_task(self.rag_pipeline.process_query_only(user_query))
        while True:
            try:
                processed = await asyncio.wait_for(asyncio.shield(query_task), timeout=15)
                break
            except asyncio.TimeoutError:
                yield json.dumps({"status": "processing", "step": 1, "message": step1_message}) + "\n"

        rewritten = processed["rewritten_query"]
        law_q = processed.get("mcp_law_query") or rewritten
        prec_q = processed.get("mcp_prec_query") or rewritten

        step2_message = "2/4 RAG 검색 + MCP 법령·판례 병렬 검색 중..."
        yield json.dumps({"status": "processing", "step": 2, "message": step2_message}) + "\n"

        loop = asyncio.get_running_loop()
        rag_task = asyncio.create_task(self.rag_pipeline.run_search_only(user_query, situation_type_key, processed))
        mcp_task = loop.run_in_executor(None, self.mcp_retriever.retrieve_sync, law_q, prec_q)
        
        step2_task = asyncio.gather(rag_task, mcp_task)
        while True:
            try:
                rag_output, mcp_evidence = await asyncio.wait_for(asyncio.shield(step2_task), timeout=15)
                break
            except asyncio.TimeoutError:
                yield json.dumps({"status": "processing", "step": 2, "message": step2_message}) + "\n"

        rag_evidence = _rag_to_evidence(rag_output)
        combined = _merge_evidence(rag_evidence, mcp_evidence)

        step3_message = "3/4 전문 AI 에이전트(법령/의결서/판례/사례) 병렬 분석 중..."
        yield json.dumps({"status": "processing", "step": 3, "message": step3_message}) + "\n"

        reports_future = loop.run_in_executor(
            None,
            self.step3_analyze,
            user_query, rag_output.rewritten_query, combined
        )
        while True:
            try:
                reports = await asyncio.wait_for(asyncio.shield(reports_future), timeout=15)
                break
            except asyncio.TimeoutError:
                yield json.dumps({"status": "processing", "step": 3, "message": step3_message}) + "\n"

        step4_message = "4/4 최종 종합 법률 보고서 생성 중..."
        yield json.dumps({"status": "processing", "step": 4, "message": step4_message}) + "\n"

        _law_docs = combined.laws
        _res_chunks = combined.resolution_chunks
        final_future = loop.run_in_executor(
            None,
            lambda: self.step4_synthesize(
                user_query, rag_output.rewritten_query, situation_type_label, reports,
                _law_docs, _res_chunks
            )
        )
        while True:
            try:
                final = await asyncio.wait_for(asyncio.shield(final_future), timeout=15)
                break
            except asyncio.TimeoutError:
                yield json.dumps({"status": "processing", "step": 4, "message": step4_message}) + "\n"

        pipeline_trace = {
            "rag": {
                "query_intent": rag_output.query_intent,
                "mcp_law_query": rag_output.mcp_law_query,
                "mcp_prec_query": rag_output.mcp_prec_query,
                "hybrid_search_results": [doc.model_dump() for doc in rag_output.hybrid_search_raw],
                "reranked_results": [doc.model_dump() for doc in rag_output.reranked_raw],
                "filtered_results": [doc.model_dump() for doc in rag_output.filtered_raw],
                "scenario_results": [doc.model_dump() for doc in rag_output.scenario_docs],
            },
            "mcp": {
                "laws": [doc.model_dump() for doc in mcp_evidence.laws],
                "precedents": [doc.model_dump() for doc in mcp_evidence.precedents],
                "ftc_decisions": [doc.model_dump() for doc in mcp_evidence.ftc_decisions],
            },
        }
        yield json.dumps({"status": "complete", "data": final.model_dump(), "pipeline_trace": pipeline_trace}) + "\n"

    # ── 내부 헬퍼 ─────────────────────────────────────────

    def _run_agents_parallel(
        self,
        original_query: str,
        rewritten_query: str,
        evidence: ExternalEvidence,
    ) -> list[AgentReport]:
        reports: list[AgentReport] = [None] * len(self.agents)  # type: ignore

        def _run_single_agent(idx, agent):
            t = time.time()
            try:
                result = agent.analyze(original_query, rewritten_query, evidence)
            except Exception as e:
                print(f"    [{agent.agent_name}] 오류 발생: {e}")
                result = AgentReport(
                    agent_type=agent.agent_type,
                    agent_name=agent.agent_name,
                    analysis=f"에이전트 실행 중 오류 발생: {e}",
                    confidence_score=0,
                    key_findings=[],
                    source_description=None,
                    limitations="에이전트 실행 실패",
                )
            print(f"    [{agent.agent_name}] 완료 ⏱ {time.time() - t:.1f}초")
            return idx, result

        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            futures = [
                executor.submit(_run_single_agent, idx, agent)
                for idx, agent in enumerate(self.agents)
            ]
            for future in as_completed(futures):
                idx, result = future.result()
                reports[idx] = result
        return reports

    def _run_agents_sequential(
        self,
        original_query: str,
        rewritten_query: str,
        evidence: ExternalEvidence,
    ) -> list[AgentReport]:
        return [agent.analyze(original_query, rewritten_query, evidence) for agent in self.agents]
