"""
CLI 진입점
사용법:
  python -m code.main "질문 내용" --situation 위반 의심 사항
  python -m code.main "질문 내용" --situation "거래 진행 중" --no-parallel
  python -m code.main "질문 내용" --output report.json
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/ 경로 추가
_BACKEND_DIR = Path(__file__).parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from models import SituationType
from agent_pipeline import LegalAnalysisPipeline

SITUATION_CHOICES = [s.value for s in SituationType]


def _print_final_report(report) -> None:
    divider = "=" * 70
    print(f"\n{divider}")
    print("  공정거래 법률 분석 최종 보고서")
    print(divider)
    print(f"\n[질문]\n{report.original_query}")
    print(f"\n[재작성 질문]\n{report.rewritten_query}")
    print(f"\n[상황 유형] {report.situation_type}")

    print(f"\n{'-' * 70}")
    print(f"  에이전트별 분석 요약")
    print(f"{'-' * 70}")
    for r in report.agent_reports:
        bar = "█" * (r.confidence_score // 10) + "░" * (10 - r.confidence_score // 10)
        print(f"\n■ {r.agent_name}  [신뢰도: {r.confidence_score}/100  {bar}]")
        for f in r.key_findings:
            print(f"   • {f}")

    print(f"\n{divider}")
    print(f"  종합 분석")
    print(divider)
    print(report.synthesis)

    print(f"\n[종합 신뢰도] {report.overall_confidence}/100")
    print(f"[리스크 수준] {report.risk_level}")
    print(f"\n[권고사항]")
    for rec in report.recommendations:
        print(f"  → {rec}")

    if report.caveats:
        print(f"\n[주의사항]\n{report.caveats}")
    print(f"\n{divider}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="공정거래 법률 분석 파이프라인")
    parser.add_argument("query", nargs="?", help="분석할 법률 질문")
    parser.add_argument(
        "--situation",
        choices=SITUATION_CHOICES,
        default=SituationType.SUSPECTED.value,
        metavar="TYPE",
        help=(
            f"상황 유형 선택 (기본: {SituationType.SUSPECTED.value})\n"
            f"선택지: {' | '.join(SITUATION_CHOICES)}"
        ),
    )
    parser.add_argument(
        "--no-parallel", action="store_true", help="에이전트를 순차적으로 실행 (기본: 병렬)"
    )
    parser.add_argument("--output", metavar="FILE", help="결과를 JSON 파일로 저장")
    parser.add_argument(
        "--model", default="gpt-4o-mini", help="사용할 OpenAI 모델 (기본: gpt-4o-mini)"
    )
    args = parser.parse_args()

    query = args.query
    if not query:
        print("질문을 입력하세요 (빈 줄 입력 시 종료):")
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        query = " ".join(lines).strip()

    if not query:
        print("질문이 입력되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    situation = SituationType(args.situation)

    try:
        pipeline = LegalAnalysisPipeline(
            model=args.model,
            parallel_agents=not args.no_parallel,
        )
        report = pipeline.run(query, situation_type=situation, verbose=True)
        _print_final_report(report)

        # results/ 자동 저장
        results_dir = Path(__file__).parent.parent / "results"
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        auto_path = results_dir / f"{timestamp}.json"
        auto_path.write_text(
            report.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"결과 저장 완료: {auto_path}")

        if args.output:
            out_path = Path(args.output)
            out_path.write_text(
                report.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"결과 저장 완료 (추가): {out_path}")

    except KeyboardInterrupt:
        print("\n중단되었습니다.", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"\n오류 발생: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
