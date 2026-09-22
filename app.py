import streamlit as st
import pandas as pd

from src.data_loader import (
    load_sample_route_features,
    find_route_feature,
    get_top_risk_routes,
)
from src.agents import run_agent_pipeline
from src.response_generator import generate_purchase_timing_report


st.set_page_config(
    page_title="항공권 가격 상승 위험도 분석",
    page_icon="✈️",
    layout="wide",
)

st.title("항공권 가격 상승 위험도 및 구매 타이밍 판단")
st.caption(
    "공공데이터 기반으로 수요·공급·환율·경쟁도·공휴일 요인을 분석하여 "
    "항공권 가격 상승 위험도와 구매 타이밍을 판단합니다."
)

try:
    sample_df = load_sample_route_features()
except Exception as e:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(e)
    st.stop()


# 사이드바
st.sidebar.header("분석 조건")

departure_airports = sorted(sample_df["departure_airport"].dropna().unique().tolist())
arrival_airports = sorted(sample_df["arrival_airport"].dropna().unique().tolist())
years = sorted(sample_df["year"].dropna().astype(int).unique().tolist())

default_departure_index = departure_airports.index("한국") if "한국" in departure_airports else 0

departure_airport = st.sidebar.selectbox(
    "출발지",
    departure_airports,
    index=default_departure_index,
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
)

selected_year = st.sidebar.selectbox(
    "분석 기준 연도",
    years,
    index=len(years) - 1,
)

departure_date = st.sidebar.date_input(
    "출발 예정일",
    value=pd.to_datetime(f"{selected_year}-01-01").date(),
)

run_button = st.sidebar.button("분석 실행", type="primary")


# 메인 데이터 미리보기
st.subheader("정제 데이터 요약")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("전체 행 수", f"{len(sample_df):,}")

with col2:
    st.metric("노선 수", f"{sample_df['route'].nunique():,}")

with col3:
    st.metric("연도 범위", f"{min(years)}~{max(years)}")

with col4:
    st.metric("평균 위험도", round(sample_df["risk_score"].mean(), 2))


with st.expander("최종 통합 피처 데이터 미리보기"):
    preview_cols = [
        "year",
        "route",
        "departure_airport",
        "arrival_airport",
        "passenger_growth_rate",
        "flight_growth_rate",
        "jpy_krw_change_rate",
        "risk_score",
        "risk_level",
        "purchase_timing_recommendation",
    ]
    preview_cols = [col for col in preview_cols if col in sample_df.columns]
    st.dataframe(sample_df[preview_cols].head(50), use_container_width=True)


# 상위 위험 노선
st.subheader("고위험 노선 예시")

try:
    top_risk_df = get_top_risk_routes(year=selected_year, limit=10)

    show_cols = [
        "year",
        "route",
        "departure_airport",
        "arrival_airport",
        "passenger_growth_rate",
        "flight_growth_rate",
        "jpy_krw_change_rate",
        "risk_score",
        "risk_level",
        "purchase_timing_recommendation",
    ]
    show_cols = [col for col in show_cols if col in top_risk_df.columns]

    st.dataframe(top_risk_df[show_cols], use_container_width=True)
except Exception as e:
    st.warning("고위험 노선 목록을 불러오지 못했습니다.")
    st.caption(str(e))


# 분석 실행
if run_button:
    st.subheader("분석 결과")

    try:
        matched_feature = find_route_feature(
            df=sample_df,
            departure_airport=departure_airport,
            arrival_airport=arrival_airport,
            departure_date=str(departure_date),
            year=selected_year,
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

        result_col1, result_col2, result_col3 = st.columns(3)

        with result_col1:
            st.metric(
                "가격 상승 위험도",
                risk_result["risk_level"],
            )

        with result_col2:
            st.metric(
                "위험도 점수",
                f"{risk_result['risk_score']} / {risk_result['max_score']}",
            )

        with result_col3:
            st.metric(
                "구매 타이밍 판단",
                risk_result["purchase_timing_recommendation"],
            )

        st.markdown("### 요인별 점수")

        factor_scores = risk_result.get("factor_scores", {})

        factor_score_df = pd.DataFrame(
            [
                {
                    "요인": "수요",
                    "점수": factor_scores.get("demand_pressure_score", 0),
                    "해석": "여객 증가율 기반",
                },
                {
                    "요인": "공급",
                    "점수": factor_scores.get("supply_pressure_score", 0),
                    "해석": "운항편 증가율 기반",
                },
                {
                    "요인": "환율",
                    "점수": factor_scores.get("exchange_pressure_score", 0),
                    "해석": "JPY/KRW 변동률 기반",
                },
                {
                    "요인": "경쟁도",
                    "점수": factor_scores.get("competition_pressure_score", 0),
                    "해석": "항공사 수 및 LCC 비중 기반",
                },
                {
                    "요인": "공휴일/연휴",
                    "점수": factor_scores.get("holiday_pressure_score", 0),
                    "해석": "공휴일 변수 기반",
                },
            ]
        )

        st.dataframe(factor_score_df, use_container_width=True)

        st.markdown("### 데이터 기반 설명")

        report = generate_purchase_timing_report(risk_result)
        st.markdown(report)

        st.markdown("### 사용된 원본 피처")

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

        st.dataframe(feature_df, use_container_width=True)

        st.warning(
            "주의: 본 결과는 실제 항공권 가격 금액 예측이 아니라, "
            "공공데이터 기반 가격 상승 위험도 및 구매 타이밍 판단 결과입니다."
        )

    except Exception as e:
        st.error("분석 실행 중 오류가 발생했습니다.")
        st.exception(e)


st.divider()

st.subheader("분석 기준")

st.markdown(
    """
- 항공 수요: 노선별 여객 증가율
- 운항 공급: 노선별 운항편 증가율
- 노선 경쟁도: 항공사 수 및 LCC 비중
- 환율: JPY/KRW 변동률
- 일정 요인: 공휴일 및 연휴 변수
- 결과: 가격 상승 위험도와 구매 타이밍 판단
"""
)