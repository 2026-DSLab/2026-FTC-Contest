import streamlit as st
import requests
import json
from datetime import datetime
from pathlib import Path

API_URL = "http://localhost:8000/diagnose"

SITUATION_TYPES = ["위반 의심 사항", "거래 진행 중", "계약 체결 전", "정기 점검"]

RISK_CONFIG = {
    "낮음":    {"emoji": "☀️",  "color": "#1db26c", "bg": "#e8faf0", "label": "저위험"},
    "보통":    {"emoji": "⛅",  "color": "#e06c00", "bg": "#fff8f0", "label": "중위험"},
    "높음":    {"emoji": "🌧️", "color": "#e02d3c", "bg": "#fff0f0", "label": "고위험"},
    "매우 높음": {"emoji": "⛈️", "color": "#c4001d", "bg": "#ffe0e0", "label": "매우 고위험"},
}

st.set_page_config(
    page_title="AI 리스크 상담 시스템",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans KR', sans-serif;
}

.main { background: #ffffff; }
.block-container { padding-top: 2rem; max-width: 780px; }

/* 헤더 */
.app-header {
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 1.5rem; border-bottom: 1px solid #e5e8ec;
    margin-bottom: 2rem;
}
.logo-icon {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #2b7de9, #0051c7);
    border-radius: 10px; display: flex; align-items: center;
    justify-content: center; color: white; font-size: 20px;
    box-shadow: 0 2px 8px rgba(43,125,233,0.3);
}
.logo-title { font-size: 1rem; font-weight: 700; color: #191f28; }
.logo-sub   { font-size: 0.7rem; color: #a0a8b4; }

/* 배지 */
.hero-badge {
    display: inline-block; padding: 5px 14px;
    background: #e8f3ff; border: 1px solid #c9e2ff;
    border-radius: 100px; font-size: 0.78rem; color: #1b64da;
    font-weight: 500; margin-bottom: 1rem;
}

/* 상황 유형 버튼 */
.stButton > button {
    border-radius: 100px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
    font-size: 0.82rem !important; font-weight: 500 !important;
    border: 1px solid #e5e8ec !important;
    background: white !important; color: #4e5968 !important;
    padding: 6px 18px !important; transition: all 0.2s !important;
}
.stButton > button:hover {
    border-color: #4593fc !important; color: #1b64da !important;
    background: #e8f3ff !important;
}

/* 진단 버튼 */
.submit-btn > button {
    background: linear-gradient(135deg, #2b7de9, #0051c7) !important;
    color: white !important; border: none !important;
    border-radius: 12px !important; padding: 12px 32px !important;
    font-size: 0.95rem !important; font-weight: 600 !important;
    box-shadow: 0 4px 14px rgba(43,125,233,0.3) !important;
    width: 100% !important;
}

/* 리스크 카드 */
.risk-card {
    text-align: center; padding: 2rem 1rem 1.5rem;
    border-radius: 16px; margin-bottom: 1.5rem;
}
.risk-emoji { font-size: 4rem; line-height: 1; margin-bottom: 0.25rem; }
.risk-score { font-size: 3rem; font-weight: 800; letter-spacing: -0.04em; }
.risk-badge-label {
    display: inline-block; padding: 4px 14px; border-radius: 100px;
    font-size: 0.85rem; font-weight: 700; margin-top: 0.4rem;
}

/* 에이전트 카드 */
.agent-card {
    border: 1px solid #e5e8ec; border-radius: 12px;
    padding: 1.25rem; margin-bottom: 1rem; background: #f8f9fb;
}
.agent-name { font-size: 0.88rem; font-weight: 700; color: #191f28; margin-bottom: 0.4rem; }
.confidence-bar-bg {
    height: 6px; background: #e5e8ec; border-radius: 3px; margin: 0.5rem 0;
}
.confidence-bar {
    height: 6px; border-radius: 3px;
    background: linear-gradient(90deg, #2b7de9, #0051c7);
}
.finding-item {
    font-size: 0.84rem; color: #4e5968; padding: 3px 0;
}
.finding-item::before { content: "• "; color: #2b7de9; font-weight: 700; }

/* 체크리스트 */
.rec-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 0.75rem 0; border-bottom: 1px solid #e5e8ec;
    font-size: 0.88rem; color: #4e5968;
}
.rec-item:last-child { border-bottom: none; }

/* 섹션 타이틀 */
.section-title {
    font-size: 1rem; font-weight: 700; color: #191f28;
    margin: 1.5rem 0 0.75rem; padding-bottom: 0.5rem;
    border-bottom: 2px solid #e8f3ff;
}

/* 구분선 */
.divider { height: 1px; background: #e5e8ec; margin: 1.25rem 0; }

/* 주의사항 */
.caveat-box {
    background: #f8f9fb; border-left: 3px solid #a0a8b4;
    border-radius: 0 8px 8px 0; padding: 0.8rem 1rem;
    font-size: 0.8rem; color: #6b7685; line-height: 1.7;
    margin-top: 1rem;
}

/* 소스 카드 */
.source-grid { display: flex; gap: 12px; margin-top: 1.5rem; }
.source-item {
    flex: 1; padding: 12px; border: 1px solid #e5e8ec;
    border-radius: 10px; text-align: center; font-size: 0.75rem; color: #6b7685;
}
.source-dot {
    display: inline-block; width: 6px; height: 6px;
    background: #1db26c; border-radius: 50; margin-right: 4px;
}
</style>
""", unsafe_allow_html=True)


def render_header():
    st.markdown("""
    <div class="app-header">
        <div class="logo-icon">⚖️</div>
        <div>
            <div class="logo-title">AI 리스크 상담 시스템</div>
            <div class="logo-sub">Corporate Compliance Advisor</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_input_page():
    render_header()

    st.markdown('<div class="hero-badge">✨ AI 기반 공정거래 리스크 진단</div>', unsafe_allow_html=True)
    st.markdown("## 거래 상황을 입력하면,\n**법적 리스크**를 진단해 드립니다")
    st.markdown(
        "<p style='color:#6b7685;font-size:0.95rem;margin-bottom:1.5rem;'>"
        "공정위 의결서, 컴플라이언스 QA, 관련 법령을 기반으로 AI가 실시간 리스크 분석 결과를 제공합니다.</p>",
        unsafe_allow_html=True,
    )

    # 상황 유형 선택
    st.markdown("<div style='font-size:0.8rem;font-weight:500;color:#6b7685;margin-bottom:0.5rem;'>상황 유형 선택</div>", unsafe_allow_html=True)
    cols = st.columns(len(SITUATION_TYPES))
    for i, sit in enumerate(SITUATION_TYPES):
        with cols[i]:
            if st.button(sit, key=f"sit_{i}"):
                st.session_state.situation = sit

    selected = st.session_state.get("situation", SITUATION_TYPES[0])
    st.markdown(
        f"<div style='font-size:0.8rem;color:#2b7de9;margin:0.3rem 0 1rem;'>선택됨: <b>{selected}</b></div>",
        unsafe_allow_html=True,
    )

    # 질문 입력
    query = st.text_area(
        "거래 상황 입력",
        placeholder="현재 기업이 처한 거래 상황을 자연어로 입력하세요\n예) 납품업체와 계약 후 단가를 10% 줄이려고 합니다. 법적으로 문제가 될까요?",
        height=160,
        key="query_input",
    )

    st.markdown('<div class="submit-btn">', unsafe_allow_html=True)
    submit = st.button("진단 시작 →", key="submit")
    st.markdown("</div>", unsafe_allow_html=True)

    # 데이터 소스 표시
    st.markdown("""
    <div style='text-align:center;font-size:0.75rem;color:#a0a8b4;margin-top:2rem;margin-bottom:0.75rem;'>
        ─── 데이터 소스 ───
    </div>
    <div class="source-grid">
        <div class="source-item"><span class="source-dot"></span>공정위 의결서 DB<br><span style='color:#a0a8b4'>심결례 데이터베이스</span></div>
        <div class="source-item"><span class="source-dot"></span>컴플라이언스 QA<br><span style='color:#a0a8b4'>질의응답 데이터베이스</span></div>
        <div class="source-item"><span class="source-dot"></span>법령·판례·결정문<br><span style='color:#a0a8b4'>국가법령정보 API</span></div>
    </div>
    """, unsafe_allow_html=True)

    if submit:
        if not query.strip():
            st.warning("거래 상황을 입력해주세요.")
            return

        with st.spinner("AI가 분석 중입니다... (1~2분 소요)"):
            try:
                resp = requests.post(
                    API_URL,
                    params={"user_query": query.strip(), "situation_type": selected},
                    timeout=300,
                )
                resp.raise_for_status()
                result = resp.json()

                # results/ 폴더에 저장
                results_dir = Path(__file__).parent / "results"
                results_dir.mkdir(exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                (results_dir / f"{ts}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                st.session_state.result = result
                st.session_state.page = "result"
                st.rerun()

            except requests.exceptions.ConnectionError:
                st.error("FastAPI 서버에 연결할 수 없습니다. `cd backend && uvicorn main:app --reload --port 8000` 을 먼저 실행해주세요.")
            except requests.exceptions.HTTPError as e:
                st.error(f"서버 오류: {e.response.status_code} — {e.response.text}")
            except Exception as e:
                st.error(f"오류 발생: {e}")


def render_result_page():
    r = st.session_state.result
    risk = r.get("risk_level", "보통")
    cfg = RISK_CONFIG.get(risk, RISK_CONFIG["보통"])

    render_header()

    # 사용자 질문
    st.markdown(
        f"<div style='background:#f8f9fb;border-radius:10px;padding:0.9rem 1.1rem;"
        f"font-size:0.9rem;color:#4e5968;margin-bottom:1.5rem;'>"
        f"<b style='color:#a0a8b4;font-size:0.75rem;'>질문</b><br>{r['original_query']}</div>",
        unsafe_allow_html=True,
    )

    # 리스크 카드
    st.markdown(
        f"""<div class="risk-card" style="background:{cfg['bg']};">
            <div class="risk-emoji">{cfg['emoji']}</div>
            <div class="risk-score" style="color:{cfg['color']};">{r['overall_confidence']}<span style="font-size:1.2rem;"> 점</span></div>
            <div class="risk-badge-label" style="background:white;color:{cfg['color']};border:1px solid {cfg['color']}20;">
                {cfg['label']} · {risk}
            </div>
            <div style="font-size:0.78rem;color:#6b7685;margin-top:0.75rem;">
                ☀️ 낮음 &nbsp;·&nbsp; ⛅ 보통 &nbsp;·&nbsp; 🌧️ 높음 &nbsp;·&nbsp; ⛈️ 매우 높음
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # 재작성 질문
    st.markdown(
        f"<div style='font-size:0.8rem;color:#6b7685;margin-bottom:1.5rem;'>"
        f"분석 쿼리: <i>{r['rewritten_query']}</i></div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 에이전트 분석
    st.markdown('<div class="section-title">에이전트별 분석</div>', unsafe_allow_html=True)
    for agent in r.get("agent_reports", []):
        score = agent["confidence_score"]
        bar_width = score
        findings_html = "".join(
            f'<div class="finding-item">{f}</div>' for f in agent.get("key_findings", [])
        )
        st.markdown(
            f"""<div class="agent-card">
                <div class="agent-name">{agent['agent_name']}</div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <div class="confidence-bar-bg" style="flex:1;">
                        <div class="confidence-bar" style="width:{bar_width}%;"></div>
                    </div>
                    <span style="font-size:0.8rem;font-weight:600;color:#2b7de9;white-space:nowrap;">
                        {score}/100
                    </span>
                </div>
                <div style="margin-top:0.5rem;">{findings_html}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 종합 분석
    st.markdown('<div class="section-title">종합 분석</div>', unsafe_allow_html=True)
    st.markdown(r.get("synthesis", ""), unsafe_allow_html=False)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 권고사항
    st.markdown('<div class="section-title">권고사항</div>', unsafe_allow_html=True)
    recs_html = "".join(
        f'<div class="rec-item"><span style="color:#2b7de9;font-weight:700;">→</span>{rec}</div>'
        for rec in r.get("recommendations", [])
    )
    st.markdown(recs_html, unsafe_allow_html=True)

    # 주의사항
    if r.get("caveats"):
        st.markdown(
            f'<div class="caveat-box">⚠️ {r["caveats"]}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 하단 버튼
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("← 새 상담", use_container_width=True):
            st.session_state.page = "input"
            st.session_state.result = None
            st.rerun()
    with col2:
        json_str = json.dumps(r, ensure_ascii=False, indent=2)
        st.download_button(
            "결과 JSON 다운로드",
            data=json_str,
            file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )


# ── 앱 진입점 ──────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "input"
if "result" not in st.session_state:
    st.session_state.result = None
if "situation" not in st.session_state:
    st.session_state.situation = SITUATION_TYPES[0]

if st.session_state.page == "input":
    render_input_page()
else:
    render_result_page()
