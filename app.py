import pandas as pd
import streamlit as st

from src.agents import run_agent_pipeline
from src.analysis_logger import save_analysis_log
from src.data_loader import load_sample_route_features, find_route_feature
from src.fallback_report import build_fallback_report, format_report_markdown
from src.llm_client import is_llm_available, generate_structured_llm_report
from src.query_parser import parse_query_with_llm
from src.response_generator import generate_user_response
from src.route_comparator import compare_routes_by_destination, get_best_route
from src.scenario_simulator import generate_date_shift_scenarios


LLM_AVAILABLE = is_llm_available()


st.set_page_config(
    page_title="항공권 구매 타이밍 의사결정 지원 서비스",
    page_icon="✈️",
    layout="wide"
)


def get_risk_badge(risk_level: str) -> str:
    if risk_level == "높음":
        return "🔴 구매를 미루기 위험한 편"
    if risk_level == "보통":
        return "🟠 며칠 더 확인 필요"
    return "🟢 비교적 여유 있음"


def get_plain_recommendation(recommendation: str) -> str:
    if recommendation == "빠른 구매 검토":
        return "일정이 고정되어 있다면 지금 가격을 확인하고 구매를 검토하는 편이 좋습니다."
    if recommendation == "가격 변동 지속 확인":
        return "지금 바로 결정하기보다 며칠간 가격 변동을 더 확인하는 것이 좋습니다."
    return "현재 조건에서는 급하게 구매하지 않고 조금 더 지켜봐도 되는 상황입니다."


def get_risk_explanation(risk_level: str) -> str:
    if risk_level == "높음":
        return (
            "여행 수요가 몰리거나, 운항편 공급이 충분하지 않거나, 연휴와 가까운 조건이 겹쳐 "
            "앞으로 항공권 선택지가 줄거나 가격이 불리해질 가능성이 큰 상태입니다."
        )
    if risk_level == "보통":
        return (
            "일부 가격 상승 요인은 있지만, 지금 바로 구매해야 할 정도로 강한 위험 신호만 있는 것은 아닙니다. "
            "가격을 며칠 더 확인하면서 판단할 수 있는 상태입니다."
        )
    return (
        "현재 입력된 조건에서는 가격이 불리해질 만한 요인이 크지 않습니다. "
        "일정에 여유가 있다면 추가 비교 후 구매를 결정할 수 있습니다."
    )


def get_top_factor_message(factors: dict) -> str:
    sorted_factors = sorted(
        factors.values(),
        key=lambda item: item["score"],
        reverse=True
    )

    top_factors = [
        factor["factor_name"]
        for factor in sorted_factors
        if factor["score"] >= 3
    ]

    if not top_factors:
        return "현재 조건에서는 특별히 강한 위험 요인이 확인되지 않았습니다."

    return f"이번 판단에 가장 크게 영향을 준 요인은 **{', '.join(top_factors[:3])}**입니다."


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


def build_input_from_feature(
    original_text: str,
    route_name: str,
    feature: dict
) -> dict:
    return {
        "original_text": original_text,
        "departure_airport": feature["departure_airport"],
        "arrival_airport": feature["arrival_airport"],
        "route_name": route_name,
        "departure_date": str(feature["departure_date"]),
        "passenger_growth_rate": float(feature["passenger_growth_rate"]),
        "flight_growth_rate": float(feature["flight_growth_rate"]),
        "days_to_holiday": int(feature["days_to_holiday"]),
        "holiday_name": str(feature["holiday_name"]),
        "jpy_krw_change_rate": float(feature["jpy_krw_change_rate"]),
        "delay_rate": float(feature["delay_rate"]),
        "cancel_count": int(feature["cancel_count"]),
    }


def build_manual_input(
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
        "passenger_growth_rate": passenger_growth_rate,
        "flight_growth_rate": flight_growth_rate,
        "days_to_holiday": days_to_holiday,
        "holiday_name": holiday_name,
        "jpy_krw_change_rate": jpy_krw_change_rate,
        "delay_rate": delay_rate,
        "cancel_count": cancel_count
    }


def show_risk_summary_message(risk: dict) -> None:
    if risk["risk_level"] == "높음":
        st.warning(risk["summary"])
    elif risk["risk_level"] == "보통":
        st.info(risk["summary"])
    else:
        st.success(risk["summary"])


@st.cache_data
def get_sample_data() -> pd.DataFrame:
    return load_sample_route_features()


try:
    sample_df = get_sample_data()
except Exception as data_error:
    st.error("샘플 데이터를 불러오지 못했습니다.")
    st.exception(data_error)
    st.stop()


st.title("항공권, 지금 사야 할까?")

st.caption(
    "공공데이터 기반으로 여행 수요, 운항편 공급, 연휴, 환율, 운항 상황을 분석해 "
    "항공권 구매를 미뤄도 되는지 판단합니다."
)

st.divider()


st.sidebar.title("여행 조건 입력")

st.sidebar.subheader("질문 입력")

original_text = st.sidebar.text_area(
    "질문",
    value="9월 말에 인천에서 도쿄 가려고 하는데 지금 사는 게 나을까?",
    height=90
)

use_query_parser = st.sidebar.toggle(
    "질문에서 여행 조건 자동 해석",
    value=LLM_AVAILABLE,
    disabled=not LLM_AVAILABLE
)

if not LLM_AVAILABLE:
    st.sidebar.caption("OpenAI API Key가 설정되지 않아 질문 자동 해석과 LLM 리포트는 비활성화됩니다.")

st.sidebar.subheader("직접 선택")

departure_airport = st.sidebar.selectbox(
    "출발 공항",
    sorted(sample_df["departure_airport"].unique().tolist()),
    format_func=lambda x: {
        "ICN": "인천(ICN)",
        "GMP": "김포(GMP)",
        "PUS": "김해(PUS)",
        "CJU": "제주(CJU)"
    }.get(x, x)
)

available_arrivals = sorted(
    sample_df[
        sample_df["departure_airport"] == departure_airport
    ]["arrival_airport"].unique().tolist()
)

arrival_airport = st.sidebar.selectbox(
    "도착 공항",
    available_arrivals,
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

matched_feature = find_route_feature(
    df=sample_df,
    departure_airport=departure_airport,
    arrival_airport=arrival_airport,
    departure_date=str(departure_date)
)

if matched_feature:
    st.sidebar.success("선택한 노선에 맞는 샘플 분석 데이터를 불러왔습니다.")
else:
    st.sidebar.warning("선택한 노선의 샘플 데이터가 없어 수동 입력값을 사용합니다.")


with st.sidebar.expander("고급 설정: 분석 변수 직접 수정", expanded=False):
    st.caption(
        "기본값은 샘플 데이터에서 자동 적용됩니다. "
        "직접 수정 옵션을 켠 경우에만 아래 값이 분석에 반영됩니다."
    )

    manual_override_enabled = st.checkbox(
        "고급 설정 값으로 분석 변수 덮어쓰기",
        value=False
    )

    if matched_feature:
        default_passenger_growth_rate = float(matched_feature["passenger_growth_rate"])
        default_flight_growth_rate = float(matched_feature["flight_growth_rate"])
        default_days_to_holiday = int(matched_feature["days_to_holiday"])
        default_holiday_name = str(matched_feature["holiday_name"])
        default_jpy_krw_change_rate = float(matched_feature["jpy_krw_change_rate"])
        default_delay_rate = float(matched_feature["delay_rate"])
        default_cancel_count = int(matched_feature["cancel_count"])
    else:
        default_passenger_growth_rate = 12.5
        default_flight_growth_rate = 2.1
        default_days_to_holiday = 2
        default_holiday_name = "추석 연휴"
        default_jpy_krw_change_rate = 3.4
        default_delay_rate = 4.2
        default_cancel_count = 0

    passenger_growth_rate = st.slider(
        "여객 수요 증가율(%)",
        min_value=-20.0,
        max_value=50.0,
        value=default_passenger_growth_rate,
        step=0.5
    )

    flight_growth_rate = st.slider(
        "운항편 증가율(%)",
        min_value=-20.0,
        max_value=50.0,
        value=default_flight_growth_rate,
        step=0.5
    )

    days_to_holiday = st.slider(
        "공휴일/연휴까지 남은 일수",
        min_value=0,
        max_value=30,
        value=default_days_to_holiday,
        step=1
    )

    holiday_name = st.text_input(
        "공휴일/연휴명",
        value=default_holiday_name
    )

    jpy_krw_change_rate = st.slider(
        "엔화 환율 변화율(%)",
        min_value=-20.0,
        max_value=30.0,
        value=default_jpy_krw_change_rate,
        step=0.1
    )

    delay_rate = st.slider(
        "운항 지연율(%)",
        min_value=0.0,
        max_value=50.0,
        value=default_delay_rate,
        step=0.1
    )

    cancel_count = st.number_input(
        "결항 건수",
        min_value=0,
        max_value=100,
        value=default_cancel_count,
        step=1
    )


st.sidebar.divider()
st.sidebar.subheader("리포트 생성 방식")

use_llm = st.sidebar.toggle(
    "LLM 설명 생성 사용",
    value=LLM_AVAILABLE,
    disabled=not LLM_AVAILABLE
)

analyze_button = st.sidebar.button(
    "구매 타이밍 분석하기",
    type="primary",
    use_container_width=True
)


if not analyze_button:
    st.subheader("항공권 구매 전, 이런 판단을 도와줍니다")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            ### 1. 지금 사야 할지 판단

            단순히 가격을 보여주는 것이 아니라,  
            **지금 구매를 미루는 것이 위험한 상황인지** 판단합니다.
            """
        )

    with col2:
        st.markdown(
            """
            ### 2. 질문을 자동 해석

            사용자가 입력한 문장에서  
            **출발지, 목적지, 출발 시기**를 추출합니다.
            """
        )

    with col3:
        st.markdown(
            """
            ### 3. 다른 선택지와 비교

            날짜를 바꾸거나 목적지를 바꿨을 때  
            **구매 위험도가 낮아지는지** 비교합니다.
            """
        )

    st.divider()

    st.subheader("현재 선택한 조건")

    selected_col1, selected_col2, selected_col3 = st.columns(3)

    with selected_col1:
        st.metric("출발 공항", departure_airport)

    with selected_col2:
        st.metric("도착 공항", arrival_airport)

    with selected_col3:
        st.metric("출발일", str(departure_date))

    if matched_feature:
        st.success(
            f"현재 선택한 {route_name} 노선은 샘플 데이터가 연결되어 있어, "
            "분석 변수가 자동으로 적용됩니다."
        )

        with st.expander("자동 적용된 분석 변수 확인"):
            st.dataframe(
                pd.DataFrame([matched_feature]),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning(
            "현재 선택한 노선은 샘플 데이터가 없어 고급 설정의 기본값으로 분석됩니다."
        )

    st.divider()

    st.subheader("분석 결과는 이렇게 해석하면 됩니다")

    st.markdown(
        """
        - **구매를 미루기 위험한 편**: 수요가 몰리거나 연휴가 가까워 가격이 불리해질 가능성이 큰 상태
        - **며칠 더 확인 필요**: 일부 위험 요인이 있어 가격 변동을 지켜볼 필요가 있는 상태
        - **비교적 여유 있음**: 현재 조건에서는 급하게 구매하지 않아도 되는 상태
        """
    )

    st.info(
        "왼쪽에서 여행 조건을 입력한 뒤 **구매 타이밍 분석하기** 버튼을 누르면 결과가 표시됩니다."
    )

    st.caption(
        "현재 MVP는 실제 항공권 가격을 직접 예측하지 않고, 공공데이터 기반 요인을 바탕으로 가격 상승 위험도를 판단합니다."
    )


if analyze_button:
    query_parse_result = None
    llm_success = False
    llm_error_message = None

    try:
        effective_departure_airport = departure_airport
        effective_arrival_airport = arrival_airport
        effective_departure_date = str(departure_date)

        if use_query_parser and LLM_AVAILABLE:
            with st.spinner("질문에서 여행 조건을 해석하는 중입니다..."):
                query_parse_result = parse_query_with_llm(original_text)

            if query_parse_result.get("parse_success"):
                effective_departure_airport = query_parse_result["departure_airport"]
                effective_arrival_airport = query_parse_result["arrival_airport"]
                effective_departure_date = query_parse_result["departure_date"]

        effective_route_name = build_route_name(
            effective_departure_airport,
            effective_arrival_airport
        )

        effective_feature = find_route_feature(
            df=sample_df,
            departure_airport=effective_departure_airport,
            arrival_airport=effective_arrival_airport,
            departure_date=effective_departure_date
        )

        if effective_feature:
            sample_input = build_input_from_feature(
                original_text=original_text,
                route_name=effective_route_name,
                feature=effective_feature
            )
        else:
            sample_input = build_manual_input(
                original_text=original_text,
                departure_airport=effective_departure_airport,
                arrival_airport=effective_arrival_airport,
                route_name=effective_route_name,
                departure_date=effective_departure_date,
                passenger_growth_rate=passenger_growth_rate,
                flight_growth_rate=flight_growth_rate,
                days_to_holiday=days_to_holiday,
                holiday_name=holiday_name,
                jpy_krw_change_rate=jpy_krw_change_rate,
                delay_rate=delay_rate,
                cancel_count=cancel_count
            )

        if manual_override_enabled:
            sample_input["passenger_growth_rate"] = passenger_growth_rate
            sample_input["flight_growth_rate"] = flight_growth_rate
            sample_input["days_to_holiday"] = days_to_holiday
            sample_input["holiday_name"] = holiday_name
            sample_input["jpy_krw_change_rate"] = jpy_krw_change_rate
            sample_input["delay_rate"] = delay_rate
            sample_input["cancel_count"] = cancel_count

        risk_result = run_agent_pipeline(sample_input)
        risk = risk_result["risk_assessment"]
        factors = risk_result["factor_analysis"]

        if use_llm and LLM_AVAILABLE:
            try:
                with st.spinner("LLM이 사용자용 설명을 생성하는 중입니다..."):
                    structured_report = generate_structured_llm_report(risk_result)
                llm_success = True
                result_text = format_report_markdown(structured_report)
            except Exception as llm_error:
                llm_success = False
                llm_error_message = str(llm_error)
                structured_report = build_fallback_report(
                    risk_result=risk_result,
                    error_message=llm_error_message
                )
                result_text = format_report_markdown(structured_report)
        else:
            structured_report = build_fallback_report(risk_result=risk_result)
            result_text = generate_user_response(risk_result)

        save_analysis_log(
            risk_result=risk_result,
            llm_used=use_llm,
            llm_success=llm_success,
            query_parse_result=query_parse_result,
            error_message=llm_error_message
        )

        st.subheader("구매 타이밍 판단 결과")

        if query_parse_result:
            with st.expander("질문 자동 해석 결과"):
                st.json(query_parse_result)

        st.markdown(
            f"""
            ### {sample_input["route_name"]} 항공권은 **{risk["recommendation"]}**가 필요합니다.

            선택한 출발일은 **{sample_input["departure_date"]}**입니다.  
            현재 조건을 보면 **{get_risk_badge(risk["risk_level"])}** 상태입니다.
            """
        )

        st.info(get_plain_recommendation(risk["recommendation"]))

        show_risk_summary_message(risk)

        st.markdown(
            f"""
            **왜 이렇게 판단했나요?**  
            {get_top_factor_message(factors)}

            **이 점수는 무엇을 의미하나요?**  
            종합 점수는 **{risk["risk_score"]}/{risk["max_score"]}점**입니다.  
            점수가 높을수록 항공권 구매를 오래 미루기 불리한 조건이 많다는 뜻입니다.
            """
        )

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("구매 판단", risk["recommendation"])

        with col2:
            st.metric("구매 지연 위험", risk["risk_level"])

        with col3:
            st.metric("종합 점수", f'{risk["risk_score"]}/{risk["max_score"]}점')

        with col4:
            st.metric("판단 신뢰도", risk["confidence"])

        with st.expander("위험도 표현 설명"):
            st.write(get_risk_explanation(risk["risk_level"]))

        st.divider()

        st.subheader("날짜를 바꾸면 더 나아질까?")

        scenario_results = generate_date_shift_scenarios(
            sample_input,
            day_shifts=[0, 3, 7]
        )

        scenario_table = pd.DataFrame([
            {
                "선택지": item["scenario_name"],
                "출발일": item["departure_date"],
                "구매 지연 위험": item["risk_level"],
                "점수": f'{item["risk_score"]}/{item["max_score"]}',
                "판단": item["recommendation"],
                "여객 증가율(%)": item["passenger_growth_rate"],
                "연휴까지 남은 일수": item["days_to_holiday"]
            }
            for item in scenario_results
        ])

        st.dataframe(
            scenario_table,
            use_container_width=True,
            hide_index=True
        )

        best_scenario = min(
            scenario_results,
            key=lambda item: item["risk_score"]
        )

        st.success(
            f"현재 입력값 기준으로는 **{best_scenario['scenario_name']}({best_scenario['departure_date']})**이 "
            f"가장 낮은 위험도({best_scenario['risk_score']}/{best_scenario['max_score']}점)로 계산됩니다."
        )

        st.caption(
            "현재 What-if는 실제 항공권 가격 예측이 아니라, 출발일 변경에 따른 연휴 인접도와 "
            "수요 집중 완화 가능성을 단순 가정하여 위험도 변화를 비교하는 기능입니다."
        )

        st.divider()

        st.subheader("같은 날짜에 다른 목적지는 어떨까?")

        route_comparison_results = compare_routes_by_destination(
            df=sample_df,
            original_text=original_text,
            departure_airport=sample_input["departure_airport"],
            departure_date=sample_input["departure_date"],
            route_name_builder=build_route_name
        )

        if route_comparison_results:
            route_comparison_table = pd.DataFrame([
                {
                    "노선": item["route_name"],
                    "출발일": item["departure_date"],
                    "구매 지연 위험": item["risk_level"],
                    "점수": f'{item["risk_score"]}/{item["max_score"]}',
                    "판단": item["recommendation"],
                    "여객 증가율(%)": item["passenger_growth_rate"],
                    "운항편 증가율(%)": item["flight_growth_rate"],
                    "연휴까지 남은 일수": item["days_to_holiday"]
                }
                for item in route_comparison_results
            ])

            st.dataframe(
                route_comparison_table,
                use_container_width=True,
                hide_index=True
            )

            best_route = get_best_route(route_comparison_results)

            if best_route:
                st.success(
                    f"같은 출발일 기준으로는 **{best_route['route_name']}** 노선이 "
                    f"가장 낮은 위험도({best_route['risk_score']}/{best_route['max_score']}점)로 계산됩니다."
                )

            st.caption(
                "목적지 비교는 같은 출발공항과 출발일을 기준으로 샘플 데이터에 존재하는 노선만 비교합니다."
            )
        else:
            st.warning("비교 가능한 다른 목적지 데이터가 없습니다.")

        st.divider()

        st.subheader("구매 판단에 영향을 준 요인")

        st.caption("각 요인은 5점 만점이며, 점수가 높을수록 항공권 구매를 미루기 불리한 요인입니다.")

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
                    value=f'{factor["score"]}/{factor["max_score"]}점'
                )

        st.divider()

        st.subheader("요인별 상세 근거")

        for factor_key, factor_label in factor_order:
            factor = factors[factor_key]

            with st.expander(f"{factor_label} | {factor['status']} / {factor['score']}/{factor['max_score']}점"):
                st.write(f"**근거**: {factor['evidence']}")
                st.write(f"**해석**: {factor['business_interpretation']}")
                st.write(f"**데이터 출처**: {factor['data_source']}")
                st.write(f"**사용 변수**: {', '.join(factor['used_features'])}")
                st.write(f"**판단 기준**: {factor['threshold']}")

        st.divider()

        st.subheader("상세 리포트")

        if use_llm and llm_success:
            st.caption("생성 방식: LLM 기반 구조화 리포트")
        elif use_llm and not llm_success:
            st.caption("생성 방식: LLM 실패 후 규칙 기반 fallback 리포트")
        else:
            st.caption("생성 방식: 규칙 기반 리포트")

        st.markdown(result_text)

        st.divider()

        with st.expander("분석 결과 JSON 확인", expanded=False):
            st.json(risk_result)

        with st.expander("What-if 시뮬레이션 원본 결과 확인", expanded=False):
            st.json(scenario_results)

        with st.expander("목적지 비교 원본 결과 확인", expanded=False):
            st.json(route_comparison_results)

    except Exception as error:
        st.error("분석 실행 중 오류가 발생했습니다.")
        st.exception(error)