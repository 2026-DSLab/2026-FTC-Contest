"""
전체 파이프라인 오케스트레이터
User Query → Query Rewriting → MCP Retrieval → 4 Agents → Synthesis → Final Report
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

from .agents import CaseAgent, LawAgent, PrecedentAgent, ResolutionAgent, SynthesisAgent
from .mcp_retriever import MCPRetriever
from .models import AgentReport, ExternalEvidence, FinalReport, RewrittenQuery
from .query_rewriter import QueryRewriter


class LegalAnalysisPipeline:
    """법률 분석 파이프라인 전체를 관리합니다."""

    def __init__(
        self,
        openai_api_key: str | None = None,
        model: str = "gpt-4o-mini",
        parallel_agents: bool = True,
    ):
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.parallel_agents = parallel_agents

        self.query_rewriter = QueryRewriter(self.client, model)
        self.mcp_retriever = MCPRetriever()
        self.agents = [
            LawAgent(self.client, model),
            ResolutionAgent(self.client, model),
            PrecedentAgent(self.client, model),
            CaseAgent(self.client, model),
        ]
        self.synthesis_agent = SynthesisAgent(self.client, model)

    # ── 단계별 메서드 (개별 호출 가능) ────────────────────

    def step1_rewrite(self, user_query: str) -> RewrittenQuery:
        """Step 1: 쿼리 재작성 및 의도 분류"""
        return self.query_rewriter.rewrite(user_query)

    def step2_retrieve(self, query: RewrittenQuery) -> ExternalEvidence:
        """Step 2: MCP를 통한 외부 법령·판례·결정문 검색"""
        return self.mcp_retriever.retrieve_sync(query.search_keywords)

    def step3_analyze(
        self, query: RewrittenQuery, evidence: ExternalEvidence
    ) -> list[AgentReport]:
        """Step 3: 4개 에이전트 병렬/순차 분석"""
        if self.parallel_agents:
            return self._run_agents_parallel(query, evidence)
        return self._run_agents_sequential(query, evidence)

    def step4_synthesize(
        self, query: RewrittenQuery, reports: list[AgentReport]
    ) -> FinalReport:
        """Step 4: 종합 분석 에이전트로 최종 레포트 생성"""
        return self.synthesis_agent.synthesize(query, reports)

    # ── 전체 실행 ──────────────────────────────────────────

    def run(self, user_query: str, verbose: bool = False) -> FinalReport:
        """전체 파이프라인을 순서대로 실행합니다."""
        if verbose:
            print(f"[1/4] 쿼리 재작성 중...")
        rewritten = self.step1_rewrite(user_query)
        if verbose:
            print(f"  → 재작성: {rewritten.rewritten}")
            print(f"  → 의도: {rewritten.intent.category.value} | {rewritten.intent.sub_intent}")

        if verbose:
            print(f"[2/4] 법령·판례 검색 중 (키워드: {rewritten.search_keywords[:3]})...")
        evidence = self.step2_retrieve(rewritten)
        if verbose:
            print(
                f"  → 법령 {len(evidence.laws)}건 / 판례 {len(evidence.precedents)}건 / "
                f"공정위 결정문 {len(evidence.ftc_decisions)}건 수집"
            )

        if verbose:
            print(f"[3/4] 다면적 법리 해석 에이전트 실행 중{'(병렬)' if self.parallel_agents else '(순차)'}...")
        reports = self.step3_analyze(rewritten, evidence)
        if verbose:
            for r in reports:
                print(f"  → [{r.agent_name}] 신뢰도: {r.confidence_score}/100")

        if verbose:
            print(f"[4/4] 최종 종합 보고서 생성 중...")
        final = self.step4_synthesize(rewritten, reports)
        if verbose:
            print(f"  → 종합 신뢰도: {final.overall_confidence}/100 | 리스크: {final.risk_level}")

        return final

    # ── 내부 헬퍼 ─────────────────────────────────────────

    def _run_agents_parallel(
        self, query: RewrittenQuery, evidence: ExternalEvidence
    ) -> list[AgentReport]:
        reports: list[AgentReport] = [None] * len(self.agents)  # type: ignore
        with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
            futures = {
                executor.submit(agent.analyze, query, evidence): idx
                for idx, agent in enumerate(self.agents)
            }
            for future in as_completed(futures):
                idx = futures[future]
                reports[idx] = future.result()
        return reports

    def _run_agents_sequential(
        self, query: RewrittenQuery, evidence: ExternalEvidence
    ) -> list[AgentReport]:
        return [agent.analyze(query, evidence) for agent in self.agents]
