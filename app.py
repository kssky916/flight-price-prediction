import streamlit as st
from src.agents import run_agent_pipeline
from src.response_generator import generate_user_response

# LLM 연결 파일이 아직 없어도 앱이 실행되도록 예외 처리
try:
    from src.llm_client import generate_llm_report
    LLM_AVAILABLE = True
except ImportError:
    generate_llm_report = None
    LLM_AVAILABLE = False


# =========================
# Page Config
# =========================

st.set_page_config(
    page_title="항공권 구매 타이밍 의사결정 지원 서비스",
    page_icon="✈️",
    layout="wide"
)


# =========================
# Helper Functions
# =========================

def get_risk_badge(risk_level: str) -> str:
    if risk_level == "높음":
        return "🔴 높음"
    if risk_level == "보통":
        return "🟠 보통"
    return "🟢 낮음"


def get_recommendation_message(recommendation: str) -> str:
    if recommendation == "빠른 구매 검토":
        return "일정이 고정되어 있다면 빠른 구매를 검토할 수 있습니다."
    if recommendation == "가격 변동 지속 확인":
        return "가격 변동을 며칠 더 확인하면서 구매 시점을 판단하는 것이 적절합니다."
    return "현재 조건에서는 급하게 구매하기보다 추가 확인 후 결정할 수 있습니다."


def build_route_name(departure_airport: str, arrival_airport: str) -> str:
    airport_name_map = {
        "ICN": "인천",
        "GMP": "김포",
        "PUS": "김해",
        "CJU": "제주",
        "NRT": "도쿄 나리타",
        "HND": "도쿄 하네다",
        "KIX": "오사카",
        "FUK": "후쿠오카",
        "CTS": "삿포로",
        "OKA": "오키나와"
    }

    departure_name = airport_name_map.get(departure_airport, departure_airport)
    arrival_name = airport_name_map.get(arrival_airport, arrival_airport)

    return f"{departure_name}-{arrival_name}"


def build_sample_input(
    original_text,
    departure_airport,
    arrival_airport,
    route_name,
    departure_date,
    passenger_growth_rate,
    flight_growth_rate,
    days_to_holiday,
    holiday_name,
    jpy_krw_change_rate,
    delay_rate,
    cancel_count
):
    return {
        "original_text": original_text,
        "departure_airport": departure_airport,
        "arrival_airport": arrival_airport,
        "route_name": route_name,
        "departure_date": str(departure_date),

        # 현재는 개발자용 테스트 변수
        # 추후 데이터분석 파트 결과값으로 교체
        "passenger_growth_rate": passenger_growth_rate,
        "flight_growth_rate": flight_growth_rate,
        "days_to_holiday": days_to_holiday,
        "holiday_name": holiday_name,
        "jpy_krw_change_rate": jpy_krw_change_rate,
        "delay_rate": delay_rate,
        "cancel_count": cancel_count
    }


# =========================
# Header
# =========================

st.title("LLM 기반 항공권 구매 타이밍 의사결정 지원 서비스")

st.caption(
    "공공데이터 기반 수요·공급·연휴·환율·운항 리스크를 활용해 "
    "항공권 가격 상승 위험도와 구매 타이밍 판단을 지원합니다."
)

st.divider()


# =========================
# Sidebar
# =========================

st.sidebar.title("분석 조건 입력")

st.sidebar.subheader("사용자 여행 조건")

original_text = st.sidebar.text_area(
    "질문",
    value="9월 말에 인천에서 도쿄 가려고 하는데 지금 사는 게 나을까?",
    height=90
)

departure_airport = st.sidebar.selectbox(
    "출발 공항",
    ["ICN", "GMP", "PUS", "CJU"],
    format_func=lambda x: {
        "ICN": "인천(ICN)",
        "GMP": "김포(GMP)",
        "PUS": "김해(PUS)",
        "CJU": "제주(CJU)"
    }.get(x, x)
)

arrival_airport = st.sidebar.selectbox(
    "도착 공항",
    ["NRT", "HND", "KIX", "FUK", "CTS", "OKA"],
    format_func=lambda x: {
        "NRT": "도쿄 나리타(NRT)",
        "HND": "도쿄 하네다(HND)",
        "KIX": "오사카(KIX)",
        "FUK": "후쿠오카(FUK)",
        "CTS": "삿포로(CTS)",
        "OKA": "오키나와(OKA)"
    }.get(x, x)
)

departure_date = st.sidebar.date_input("출발일")

route_name = build_route_name(departure_airport, arrival_airport)


# =========================
# Advanced Input
# =========================

with st.sidebar.expander("개발자용 분석 변수 설정", expanded=False):
    st.caption("현재는 데이터분석 파트 결과값이 없으므로 임시 변수로 테스트합니다.")

    passenger_growth_rate = st.slider(
        "여객 수요 증가율(%)",
        min_value=-20.0,
        max_value=50.0,
        value=12.5,
        step=0.5
    )

    flight_growth_rate = st.slider(
        "운항편 증가율(%)",
        min_value=-20.0,
        max_value=50.0,
        value=2.1,
        step=0.5
    )

    days_to_holiday = st.slider(
        "공휴일/연휴까지 남은 일수",
        min_value=0,
        max_value=30,
        value=2,
        step=1
    )

    holiday_name = st.text_input(
        "공휴일/연휴명",
        value="추석 연휴"
    )

    jpy_krw_change_rate = st.slider(
        "엔화 환율 변화율(%)",
        min_value=-20.0,
        max_value=30.0,
        value=3.4,
        step=0.1
    )

    delay_rate = st.slider(
        "운항 지연율(%)",
        min_value=0.0,
        max_value=50.0,
        value=4.2,
        step=0.1
    )

    cancel_count = st.number_input(
        "결항 건수",
        min_value=0,
        max_value=100,
        value=0,
        step=1
    )


# =========================
# LLM Option
# =========================

st.sidebar.divider()
st.sidebar.subheader("리포트 생성 방식")

use_llm = st.sidebar.toggle(
    "LLM 설명 생성 사용",
    value=False,
    disabled=not LLM_AVAILABLE
)

if not LLM_AVAILABLE:
    st.sidebar.caption("현재 src/llm_client.py가 없어 규칙 기반 리포트만 사용합니다.")


analyze_button = st.sidebar.button(
    "분석 실행",
    type="primary",
    use_container_width=True
)


# =========================
# Default Main View
# =========================

if not analyze_button:
    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        st.subheader("서비스 개요")
        st.write(
            """
            이 서비스는 항공권 실제 가격을 직접 예측하는 대신,  
            공공데이터 기반으로 가격 상승 가능성에 영향을 줄 수 있는 요인을 분석합니다.
            """
        )

        st.markdown(
            """
            **분석에 반영되는 주요 요인**
            - 노선별 여객 수요 변화
            - 운항편 공급 변화
            - 공휴일 및 연휴 인접 여부
            - 엔화 환율 변화
            - 지연·결항 등 운항 리스크
            """
        )

    with right_col:
        st.subheader("현재 MVP 범위")
        st.info(
            """
            현재 버전은 데이터분석 결과값을 임시 입력값으로 넣어  
            Agent 기반 위험도 산정과 사용자용 리포트 생성을 테스트하는 단계입니다.
            """
        )

    st.warning("왼쪽 사이드바에서 조건을 입력한 뒤 `분석 실행` 버튼을 눌러주세요.")


# =========================
# Analysis Execution
# =========================

if analyze_button:
    sample_input = build_sample_input(
        original_text=original_text,
        departure_airport=departure_airport,
        arrival_airport=arrival_airport,
        route_name=route_name,
        departure_date=departure_date,
        passenger_growth_rate=passenger_growth_rate,
        flight_growth_rate=flight_growth_rate,
        days_to_holiday=days_to_holiday,
        holiday_name=holiday_name,
        jpy_krw_change_rate=jpy_krw_change_rate,
        delay_rate=delay_rate,
        cancel_count=cancel_count
    )

    risk_result = run_agent_pipeline(sample_input)

    if use_llm and LLM_AVAILABLE:
        with st.spinner("LLM이 구매 타이밍 리포트를 생성하는 중입니다..."):
            result_text = generate_llm_report(risk_result)
    else:
        result_text = generate_user_response(risk_result)

    risk = risk_result["risk_assessment"]
    factors = risk_result["factor_analysis"]

    # =========================
    # Summary Section
    # =========================

    st.subheader("분석 결과 요약")

    st.markdown(
        f"""
        ### {route_name} 항공권 구매 타이밍 분석

        선택한 출발일은 **{departure_date}**이며,  
        공공데이터 기반 가격 상승 위험도는 **{get_risk_badge(risk["risk_level"])}**입니다.
        """
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("위험도 등급", risk["risk_level"])

    with col2:
        st.metric("위험도 점수", f'{risk["risk_score"]}점')

    with col3:
        st.metric("구매 판단", risk["recommendation"])

    with col4:
        st.metric("판단 신뢰도", risk["confidence"])

    st.info(get_recommendation_message(risk["recommendation"]))
    st.caption(risk["summary"])

    st.divider()


    # =========================
    # Factor Overview
    # =========================

    st.subheader("요인별 위험도")

    factor_order = [
        ("demand", "수요"),
        ("supply", "공급"),
        ("holiday", "연휴/시기"),
        ("exchange_rate", "환율"),
        ("operation", "운항 상황")
    ]

    factor_cols = st.columns(5)

    for col, (factor_key, factor_label) in zip(factor_cols, factor_order):
        factor = factors[factor_key]

        with col:
            st.markdown(f"**{factor_label}**")
            st.metric(
                label=factor["status"],
                value=f'{factor["score"]}점'
            )

    st.divider()


    # =========================
    # Agent Detail
    # =========================

    st.subheader("Agent별 판단 근거")

    for factor_key, factor_label in factor_order:
        factor = factors[factor_key]

        with st.expander(f"{factor_label} Agent | {factor['status']} / {factor['score']}점"):
            st.write(f"**근거**: {factor['evidence']}")
            st.write(f"**해석**: {factor['business_interpretation']}")

    st.divider()


    # =========================
    # Final Report
    # =========================

    st.subheader("구매 타이밍 리포트")

    if use_llm and LLM_AVAILABLE:
        st.caption("생성 방식: LLM 기반 리포트")
    else:
        st.caption("생성 방식: 규칙 기반 리포트")

    st.markdown(result_text)

    st.divider()


    # =========================
    # Raw Data Debug
    # =========================

    with st.expander("분석 결과 JSON 확인", expanded=False):
        st.json(risk_result)