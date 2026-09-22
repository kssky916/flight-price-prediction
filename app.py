from pathlib import Path
from datetime import timedelta

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components

from src.data_loader import (
    load_sample_route_features,
    find_route_feature,
)
from src.agents import run_agent_pipeline
from src.response_generator import generate_purchase_timing_report


st.set_page_config(
    page_title="항공권 가격 상승 위험도 분석",
    page_icon="✈️",
    layout="wide",
)


AIRPORT_DISPLAY_NAMES = {
    "ICN": "인천(ICN)",
    "GMP": "김포(GMP)",
    "PUS": "부산/김해(PUS)",
    "CJU": "제주(CJU)",
    "NRT": "도쿄 나리타(NRT)",
    "HND": "도쿄 하네다(HND)",
    "KIX": "오사카 간사이(KIX)",
    "FUK": "후쿠오카(FUK)",
    "CTS": "삿포로(CTS)",
    "OKA": "오키나와(OKA)",
    "NGO": "나고야(NGO)",
    "UKB": "고베(UKB)",
    "KMJ": "구마모토(KMJ)",
    "HIJ": "히로시마(HIJ)",
    "MYJ": "마쓰야마(MYJ)",
    "KOJ": "가고시마(KOJ)",
    "OIT": "오이타(OIT)",
    "KMI": "미야자키(KMI)",
    "TAK": "다카마쓰(TAK)",
    "SDJ": "센다이(SDJ)",
    "AOJ": "아오모리(AOJ)",
    "FSZ": "시즈오카(FSZ)",
    "KIJ": "니가타(KIJ)",
    "OKJ": "오카야마(OKJ)",
    "YGJ": "요나고(YGJ)",
    "KKJ": "기타큐슈(KKJ)",
    "ISG": "이시가키(ISG)",
    "NGS": "나가사키(NGS)",
}


HOLIDAY_PATH = Path("data/processed/processed_holidays_clean.csv")


def display_airport(value):
    value = str(value).strip()

    if "(" in value and ")" in value:
        code = value.split("(")[-1].split(")")[0].strip()
        if code in AIRPORT_DISPLAY_NAMES:
            return AIRPORT_DISPLAY_NAMES[code]

    if value in AIRPORT_DISPLAY_NAMES:
        return AIRPORT_DISPLAY_NAMES[value]

    name_map = {
        "한국": "인천(ICN)",
        "인천": "인천(ICN)",
        "김포": "김포(GMP)",
        "부산": "부산/김해(PUS)",
        "김해": "부산/김해(PUS)",
        "제주": "제주(CJU)",
        "도쿄": "도쿄 나리타(NRT)",
        "나리타": "도쿄 나리타(NRT)",
        "하네다": "도쿄 하네다(HND)",
        "오사카": "오사카 간사이(KIX)",
        "간사이": "오사카 간사이(KIX)",
        "후쿠오카": "후쿠오카(FUK)",
        "삿포로": "삿포로(CTS)",
        "오키나와": "오키나와(OKA)",
        "나고야": "나고야(NGO)",
        "고베": "고베(UKB)",
        "구마모토": "구마모토(KMJ)",
        "구마모도": "구마모토(KMJ)",
        "히로시마": "히로시마(HIJ)",
        "마쓰야마": "마쓰야마(MYJ)",
        "가고시마": "가고시마(KOJ)",
        "오이타": "오이타(OIT)",
        "미야자키": "미야자키(KMI)",
        "다카마쓰": "다카마쓰(TAK)",
        "센다이": "센다이(SDJ)",
        "아오모리": "아오모리(AOJ)",
        "시즈오카": "시즈오카(FSZ)",
        "니가타": "니가타(KIJ)",
        "오카야마": "오카야마(OKJ)",
        "요나고": "요나고(YGJ)",
        "기타큐슈": "기타큐슈(KKJ)",
        "이시가키": "이시가키(ISG)",
        "나가사키": "나가사키(NGS)",
    }

    return name_map.get(value, value)


def render_metric_card(title, value, caption=""):
    st.markdown(
        f"""
        <div style="
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: 22px;
            background-color: #FFFFFF;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            min-height: 126px;
        ">
            <div style="font-size: 14px; color: #6B7280; margin-bottom: 10px;">{title}</div>
            <div style="font-size: 30px; font-weight: 700; color: #111827;">{value}</div>
            <div style="font-size: 13px; color: #6B7280; margin-top: 10px;">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_risk_color(risk_level):
    if risk_level == "높음":
        return "#DC2626"
    if risk_level == "중간":
        return "#D97706"
    return "#16A34A"


def get_decision_message(risk_level):
    if risk_level == "높음":
        return "지금은 빠르게 구매를 검토하는 편이 좋습니다."
    if risk_level == "중간":
        return "바로 확정하기보다 가격을 조금 더 모니터링한 뒤 구매하는 편이 적절합니다."
    return "현재 조건에서는 급하게 구매하지 않고 조금 더 지켜봐도 됩니다."


def select_analysis_year(available_years, departure_date):
    target_year = pd.to_datetime(departure_date).year
    available_years = sorted([int(year) for year in available_years])

    if target_year in available_years:
        return target_year

    past_years = [year for year in available_years if year <= target_year]

    if past_years:
        return max(past_years)

    return max(available_years)


def scroll_to_analysis_top():
    components.html(
        """
        <script>
            const doc = window.parent.document;
            const target = doc.getElementById("analysis-result-top");
            if (target) {
                setTimeout(() => {
                    target.scrollIntoView({ behavior: "smooth", block: "start" });
                }, 150);
            }
        </script>
        """,
        height=0,
    )


def load_recommendation_dates(limit=5):
    today = pd.Timestamp.today().normalize()

    if HOLIDAY_PATH.exists():
        holiday_df = pd.read_csv(HOLIDAY_PATH, encoding="utf-8-sig")
        holiday_df["holiday_date"] = pd.to_datetime(
            holiday_df["holiday_date"],
            errors="coerce",
        )

        future_holidays = (
            holiday_df[holiday_df["holiday_date"] >= today]
            .dropna(subset=["holiday_date"])
            .sort_values("holiday_date")
            .drop_duplicates(subset=["holiday_date"])
        )

        dates = future_holidays["holiday_date"].head(limit).tolist()

        if len(dates) >= limit:
            return dates

    return [today + timedelta(days=30 + i * 14) for i in range(limit)]


def build_buy_now_recommendations(df, limit=5):
    current_year = pd.Timestamp.today().year
    available_years = sorted(df["year"].dropna().astype(int).unique().tolist())

    usable_years = [year for year in available_years if year <= current_year]

    if usable_years:
        base_year = max(usable_years)
    else:
        base_year = max(available_years)

    target_df = df[df["year"] == base_year].copy()

    if target_df.empty:
        target_df = df.copy()

    if "purchase_timing_recommendation" in target_df.columns:
        priority_df = target_df[
            target_df["purchase_timing_recommendation"]
            .astype(str)
            .str.contains("빠른 구매", na=False)
        ].copy()

        if not priority_df.empty:
            target_df = priority_df

    sort_cols = [col for col in ["risk_score", "passenger_growth_rate"] if col in target_df.columns]

    if sort_cols:
        target_df = target_df.sort_values(sort_cols, ascending=[False] * len(sort_cols))

    target_df = (
        target_df
        .drop_duplicates(subset=["departure_airport", "arrival_airport"])
        .head(limit)
        .copy()
    )

    recommendation_dates = load_recommendation_dates(limit)

    rows = []

    for idx, (_, row) in enumerate(target_df.iterrows()):
        departure_date = recommendation_dates[idx % len(recommendation_dates)]
        arrival_date = departure_date + timedelta(days=3)

        risk_level = str(row.get("risk_level", ""))
        risk_score = row.get("risk_score", "")

        rows.append(
            {
                "순위": idx + 1,
                "추천 노선": f"{display_airport(row['departure_airport'])} → {display_airport(row['arrival_airport'])}",
                "추천 일정": f"{departure_date.strftime('%Y-%m-%d')} ~ {arrival_date.strftime('%Y-%m-%d')}",
                "위험도": f"{risk_level} · {risk_score}점",
                "구매 판단": row.get("purchase_timing_recommendation", ""),
            }
        )

    return pd.DataFrame(rows)


def render_buy_now_recommendations(df):
    st.markdown("### 지금 구매 검토하기 좋은 추천 노선")
    st.caption(
        "가격 상승 위험도와 구매 타이밍 판단 결과를 기준으로 우선 확인해볼 만한 노선입니다."
    )

    recommendation_df = build_buy_now_recommendations(df, limit=5)

    if recommendation_df.empty:
        st.info("추천할 수 있는 노선 데이터가 없습니다.")
        return

    recommendation_df = recommendation_df[
        [
            "순위",
            "추천 노선",
            "추천 일정",
            "위험도",
            "구매 판단",
        ]
    ]

    st.table(recommendation_df)


def render_analysis_result(risk_result, matched_feature, arrival_date):
    scroll_to_analysis_top()

    st.markdown('<div id="analysis-result-top"></div>', unsafe_allow_html=True)

    risk_level = risk_result["risk_level"]
    risk_color = get_risk_color(risk_level)

    departure_display = display_airport(risk_result["departure_airport"])
    arrival_display = display_airport(risk_result["arrival_airport"])
    decision_message = get_decision_message(risk_result["risk_level"])

    st.markdown("---")

    st.markdown(
        f"""
        <div style="
            border-radius: 22px;
            padding: 34px;
            background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 100%);
            border: 1px solid #E5E7EB;
            margin-bottom: 28px;
        ">
            <div style="font-size: 15px; color: #6B7280; margin-bottom: 10px;">
                분석 완료
            </div>
            <div style="font-size: 34px; font-weight: 800; color: #111827; margin-bottom: 12px;">
                {departure_display} → {arrival_display} 노선 분석 결과
            </div>
            <div style="font-size: 18px; color: #374151; margin-bottom: 8px;">
                여행 일정: {risk_result["departure_date"]} ~ {arrival_date}
            </div>
            <div style="font-size: 18px; color: #374151; margin-bottom: 22px;">
                가격 상승 위험도는 
                <span style="font-weight: 800; color: {risk_color};">{risk_level}</span>입니다.
            </div>
            <div style="
                border-radius: 16px;
                background-color: #FFFFFF;
                padding: 26px;
                border: 1px solid #E5E7EB;
            ">
                <div style="font-size: 15px; color: #6B7280; margin-bottom: 8px;">
                    구매 판단
                </div>
                <div style="font-size: 34px; font-weight: 800; color: {risk_color}; margin-bottom: 8px;">
                    {risk_result["purchase_timing_recommendation"]}
                </div>
                <div style="font-size: 18px; color: #111827; line-height: 1.55;">
                    {decision_message}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    result_col1, result_col2, result_col3 = st.columns(3)

    with result_col1:
        render_metric_card(
            "가격 상승 위험도",
            risk_result["risk_level"],
            "높을수록 빠른 구매 검토",
        )

    with result_col2:
        render_metric_card(
            "위험도 점수",
            f"{risk_result['risk_score']} / {risk_result['max_score']}",
            "100점 기준",
        )

    with result_col3:
        render_metric_card(
            "구매 타이밍",
            risk_result["purchase_timing_recommendation"],
            "사용자 의사결정 가이드",
        )

    st.markdown("<div style='height: 34px;'></div>", unsafe_allow_html=True)

    with st.expander("판단 근거 자세히 보기", expanded=False):
        st.markdown("### 요인별 점수")

        factor_scores = risk_result.get("factor_scores", {})

        factor_score_df = pd.DataFrame(
            [
                {
                    "요인": "수요-공급 불균형",
                    "점수": factor_scores.get("demand_supply_gap_score", 0),
                    "해석": "여객 증가율과 운항편 증가율의 차이 기반",
                },
                {
                    "요인": "운항 공급",
                    "점수": factor_scores.get("supply_pressure_score", 0),
                    "해석": "운항편 증가율 기반",
                },
                {
                    "요인": "노선 경쟁도",
                    "점수": factor_scores.get("competition_pressure_score", 0),
                    "해석": "항공사 수 및 LCC 비중 기반",
                },
                {
                    "요인": "공휴일/연휴",
                    "점수": factor_scores.get("holiday_pressure_score", 0),
                    "해석": "공휴일 및 연휴 변수 기반",
                },
                {
                    "요인": "환율",
                    "점수": factor_scores.get("exchange_pressure_score", 0),
                    "해석": "JPY/KRW 변동률 기반, 낮은 가중치",
                },
            ]
        )

        st.dataframe(factor_score_df, use_container_width=True, hide_index=True)

        st.markdown("### 데이터 기반 설명")
        report = generate_purchase_timing_report(risk_result)
        st.markdown(report)

        st.markdown("### 사용된 주요 피처")

        feature_cols = [
            "year",
            "route",
            "departure_airport",
            "arrival_airport",
            "passenger_growth_rate",
            "flight_growth_rate",
            "passengers_per_flight",
            "avg_carrier_count",
            "avg_lcc_share",
            "jpy_krw_rate",
            "jpy_krw_change_rate",
            "holiday_count",
            "risk_score",
            "risk_level",
            "purchase_timing_recommendation",
        ]

        feature_cols = [col for col in feature_cols if col in matched_feature]

        feature_df = pd.DataFrame(
            [{"항목": col, "값": matched_feature.get(col)} for col in feature_cols]
        )

        st.dataframe(feature_df, use_container_width=True, hide_index=True)


st.title("항공권 가격 상승 위험도 및 구매 타이밍 판단")
st.caption(
    "공공데이터 기반으로 항공 수요, 운항 공급, 노선 경쟁도, 공휴일, 환율 요인을 분석하여 "
    "항공권 가격 상승 위험도와 구매 타이밍을 판단합니다."
)

try:
    sample_df = load_sample_route_features()
except Exception as e:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(e)
    st.stop()


if "analysis_result" not in st.session_state:
    st.session_state["analysis_result"] = None

if "matched_feature" not in st.session_state:
    st.session_state["matched_feature"] = None

if "arrival_date" not in st.session_state:
    st.session_state["arrival_date"] = None

if "last_selected_key" not in st.session_state:
    st.session_state["last_selected_key"] = None


st.sidebar.header("분석 조건")

departure_airports = sorted(sample_df["departure_airport"].dropna().unique().tolist())
available_years = sorted(sample_df["year"].dropna().astype(int).unique().tolist())

default_departure_index = departure_airports.index("한국") if "한국" in departure_airports else 0

departure_airport = st.sidebar.selectbox(
    "출발지",
    departure_airports,
    index=default_departure_index,
    format_func=display_airport,
)

arrival_candidates = sample_df[
    sample_df["departure_airport"] == departure_airport
]["arrival_airport"].dropna().unique().tolist()

arrival_candidates = sorted(arrival_candidates)

if not arrival_candidates:
    st.error("선택한 출발지에 해당하는 도착지가 없습니다.")
    st.stop()

arrival_airport = st.sidebar.selectbox(
    "도착지",
    arrival_candidates,
    format_func=display_airport,
)

today_date = pd.Timestamp.today().date()

departure_date = st.sidebar.date_input(
    "출발 예정일",
    value=today_date + timedelta(days=30),
)

arrival_date = st.sidebar.date_input(
    "도착 예정일",
    value=departure_date + timedelta(days=3),
)

if arrival_date < departure_date:
    st.sidebar.error("도착 예정일은 출발 예정일 이후여야 합니다.")

analysis_year = select_analysis_year(available_years, departure_date)

current_selected_key = f"{departure_airport}|{arrival_airport}|{departure_date}|{arrival_date}"

if (
    st.session_state["last_selected_key"] is not None
    and st.session_state["last_selected_key"] != current_selected_key
):
    st.session_state["analysis_result"] = None
    st.session_state["matched_feature"] = None
    st.session_state["arrival_date"] = None

run_button = st.sidebar.button("분석 실행", type="primary", use_container_width=True)
reset_button = st.sidebar.button("분석 초기화", use_container_width=True)

if reset_button:
    st.session_state["analysis_result"] = None
    st.session_state["matched_feature"] = None
    st.session_state["arrival_date"] = None
    st.session_state["last_selected_key"] = None
    st.rerun()


if run_button:
    if arrival_date < departure_date:
        st.error("도착 예정일은 출발 예정일 이후여야 합니다.")
    else:
        try:
            matched_feature = find_route_feature(
                df=sample_df,
                departure_airport=departure_airport,
                arrival_airport=arrival_airport,
                departure_date=str(departure_date),
                year=analysis_year,
            )

            sample_input = {
                **matched_feature,
                "departure_airport": matched_feature.get("departure_airport", departure_airport),
                "arrival_airport": matched_feature.get("arrival_airport", arrival_airport),
                "departure_date": str(departure_date),
                "passenger_growth_rate": matched_feature.get("passenger_growth_rate", 0),
                "flight_growth_rate": matched_feature.get("flight_growth_rate", 0),
                "days_to_holiday": matched_feature.get("days_to_holiday", 0),
                "holiday_name": matched_feature.get("holiday_name", ""),
                "holiday_count": matched_feature.get("holiday_count", 0),
                "jpy_krw_change_rate": matched_feature.get("jpy_krw_change_rate", 0),
                "delay_rate": matched_feature.get("delay_rate", 0),
                "cancel_count": matched_feature.get("cancel_count", 0),
                "avg_carrier_count": matched_feature.get("avg_carrier_count", 0),
                "avg_lcc_share": matched_feature.get("avg_lcc_share", 0),
            }

            risk_result = run_agent_pipeline(sample_input)

            st.session_state["analysis_result"] = risk_result
            st.session_state["matched_feature"] = matched_feature
            st.session_state["arrival_date"] = str(arrival_date)
            st.session_state["last_selected_key"] = current_selected_key

            st.rerun()

        except Exception as e:
            st.error("분석 실행 중 오류가 발생했습니다.")
            st.exception(e)


if st.session_state["analysis_result"] is not None:
    render_analysis_result(
        st.session_state["analysis_result"],
        st.session_state["matched_feature"],
        st.session_state["arrival_date"],
    )

else:
    st.markdown("### 항공권 구매 타이밍을 확인해보세요")

    st.markdown(
        """
        왼쪽 사이드바에서 **출발지, 도착지, 출발 예정일, 도착 예정일**을 선택한 뒤  
        **분석 실행** 버튼을 누르면 구매 타이밍 판단 결과가 표시됩니다.
        """
    )

    guide_col1, guide_col2, guide_col3 = st.columns(3)

    with guide_col1:
        render_metric_card(
            "1단계",
            "노선 선택",
            "출발지와 도착지를 선택합니다.",
        )

    with guide_col2:
        render_metric_card(
            "2단계",
            "여행 일정 입력",
            "출발 예정일과 도착 예정일을 선택합니다.",
        )

    with guide_col3:
        render_metric_card(
            "3단계",
            "구매 판단 확인",
            "가격 상승 위험도와 구매 타이밍을 확인합니다.",
        )

    st.markdown("<div style='height: 44px;'></div>", unsafe_allow_html=True)

    render_buy_now_recommendations(sample_df)


st.markdown("---")

with st.expander("분석 기준 보기", expanded=False):
    st.markdown(
        """
- 항공 수요: 노선별 여객 증가율
- 운항 공급: 노선별 운항편 증가율
- 수요-공급 불균형: 여객 증가율과 운항편 증가율의 차이
- 노선 경쟁도: 항공사 수 및 LCC 비중
- 일정 요인: 공휴일 및 연휴 변수
- 환율: JPY/KRW 변동률, 낮은 가중치
- 결과: 가격 상승 위험도와 구매 타이밍 판단
"""
    )