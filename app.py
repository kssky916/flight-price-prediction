from datetime import timedelta
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.data_loader import load_sample_route_features
from src.api_client import analyze_route_via_api, recommend_text_via_api


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


def display_airport(value):
    value = str(value).strip()

    if "(" in value and ")" in value:
        code = value.split("(")[-1].split(")")[0].strip()

        if code in AIRPORT_DISPLAY_NAMES:
            return AIRPORT_DISPLAY_NAMES[code]

    if value in AIRPORT_DISPLAY_NAMES:
        return AIRPORT_DISPLAY_NAMES[value]

    return value


def inject_global_style():
    st.markdown(
        """
        <style>
        .result-fade-in {
            animation: result-fade-in 0.55s ease-out;
        }

        @keyframes result-fade-in {
            from {
                opacity: 0;
                transform: translateY(12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        div[data-testid="stTextArea"] textarea {
            min-height: 150px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
            <div style="font-size: 28px; font-weight: 700; color: #111827; word-break: keep-all;">{value}</div>
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


def render_loading_overlay(stage_text):
    return f"""
    <style>
    .loading-overlay {{
        position: fixed;
        inset: 0;
        z-index: 999999;
        background: rgba(248, 250, 252, 0.58);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        display: flex;
        align-items: center;
        justify-content: center;
    }}

    .loading-card {{
        width: 420px;
        padding: 38px 34px;
        border-radius: 28px;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(229, 231, 235, 0.95);
        box-shadow: 0 28px 80px rgba(15, 23, 42, 0.18);
        text-align: center;
        animation: loading-card-in 0.35s ease-out;
    }}

    .plane-wrap {{
        width: 82px;
        height: 82px;
        margin: 0 auto 20px auto;
        border-radius: 999px;
        background: linear-gradient(135deg, #EEF2FF 0%, #DBEAFE 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        animation: plane-float 1.8s ease-in-out infinite;
    }}

    .plane-svg {{
        width: 46px;
        height: 46px;
    }}

    .loading-title {{
        font-size: 26px;
        font-weight: 850;
        color: #111827;
        margin-bottom: 10px;
    }}

    .loading-stage {{
        font-size: 16px;
        color: #374151;
        line-height: 1.65;
        margin-bottom: 24px;
    }}

    .progress-track {{
        width: 100%;
        height: 8px;
        border-radius: 999px;
        overflow: hidden;
        background: #E5E7EB;
        margin-bottom: 14px;
    }}

    .progress-bar {{
        width: 48%;
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #2563EB, #60A5FA);
        animation: progress-move 1.35s ease-in-out infinite;
    }}

    .loading-sub {{
        font-size: 13px;
        color: #6B7280;
    }}

    @keyframes plane-float {{
        0% {{ transform: translateY(0px) rotate(-8deg); }}
        50% {{ transform: translateY(-9px) rotate(2deg); }}
        100% {{ transform: translateY(0px) rotate(-8deg); }}
    }}

    @keyframes progress-move {{
        0% {{ transform: translateX(-80%); }}
        50% {{ transform: translateX(70%); }}
        100% {{ transform: translateX(220%); }}
    }}

    @keyframes loading-card-in {{
        from {{
            opacity: 0;
            transform: translateY(14px) scale(0.98);
        }}
        to {{
            opacity: 1;
            transform: translateY(0) scale(1);
        }}
    }}
    </style>

    <div class="loading-overlay">
        <div class="loading-card">
            <div class="plane-wrap">
                <svg class="plane-svg" viewBox="0 0 24 24" fill="none">
                    <path d="M2.5 13.5L21 3.5L15.5 21L11.5 14.5L2.5 13.5Z"
                          fill="#2563EB"/>
                    <path d="M11.5 14.5L21 3.5L8.5 12.8"
                          stroke="white"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"/>
                </svg>
            </div>
            <div class="loading-title">분석 중입니다</div>
            <div class="loading-stage">{stage_text}</div>
            <div class="progress-track">
                <div class="progress-bar"></div>
            </div>
            <div class="loading-sub">잠시만 기다려주세요.</div>
        </div>
    </div>
    """


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

    today = pd.Timestamp.today().normalize()
    recommendation_dates = [today + timedelta(days=30 + i * 14) for i in range(limit)]

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

    st.dataframe(
        recommendation_df,
        use_container_width=True,
        hide_index=True,
    )


def render_parsed_request(parsed_request):
    cards = []

    travel_start = parsed_request.get("travel_window_start")
    travel_end = parsed_request.get("travel_window_end")

    if travel_start and travel_end:
        cards.append(
            {
                "title": "여행 가능 기간",
                "value": f"{travel_start} ~ {travel_end}",
                "caption": "입력한 기간 조건",
            }
        )

    nights = parsed_request.get("nights")
    days = parsed_request.get("days")

    if nights and days:
        cards.append(
            {
                "title": "희망 체류 기간",
                "value": f"{nights}박 {days}일",
                "caption": "입력한 체류 조건",
            }
        )

    destination_text = parsed_request.get("destination_city") or parsed_request.get("destination_country")

    if destination_text:
        cards.append(
            {
                "title": "목적지 조건",
                "value": destination_text,
                "caption": "입력한 목적지 조건",
            }
        )

    holiday_names = parsed_request.get("must_include_holiday_names") or []

    if holiday_names:
        cards.append(
            {
                "title": "포함 조건",
                "value": ", ".join(holiday_names),
                "caption": "입력한 공휴일·이벤트 조건",
            }
        )

    if not cards:
        return

    st.markdown("### AI가 추출한 여행 조건")

    cols = st.columns(len(cards))

    for col, card in zip(cols, cards):
        with col:
            render_metric_card(
                card["title"],
                card["value"],
                card["caption"],
            )


def render_natural_recommendations(parsed_request, recommendations, top_ai_report):
    scroll_to_analysis_top()

    st.markdown('<div id="analysis-result-top"></div>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown(
        """
        <div class="result-fade-in">
            <div style="
                border-radius: 22px;
                padding: 34px;
                background: linear-gradient(135deg, #F8FAFC 0%, #EEF2FF 100%);
                border: 1px solid #E5E7EB;
                margin-bottom: 28px;
            ">
                <div style="font-size: 15px; color: #6B7280; margin-bottom: 10px;">
                    텍스트 기반 추천 완료
                </div>
                <div style="font-size: 34px; font-weight: 800; color: #111827; margin-bottom: 12px;">
                    입력한 여행 조건에 맞는 구매 검토 노선을 추천합니다
                </div>
                <div style="font-size: 18px; color: #374151; line-height: 1.55;">
                    AI가 사용자의 문장에서 필요한 여행 조건을 추출하고,
                    FastAPI 백엔드가 기존 위험도 산정 로직으로 후보 노선을 비교했습니다.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_parsed_request(parsed_request)

    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

    rows = []

    for idx, item in enumerate(recommendations, start=1):
        rows.append(
            {
                "순위": idx,
                "추천 노선": f"{display_airport(item['departure_airport'])} → {display_airport(item['arrival_airport'])}",
                "추천 일정": f"{item['departure_date']} ~ {item['return_date']}",
                "위험도": f"{item['risk_level']} · {item['risk_score']}점",
                "구매 판단": item["purchase_timing_recommendation"],
            }
        )

    recommendation_df = pd.DataFrame(rows)

    st.markdown("### 추천 결과")
    st.caption("동일 노선이 반복되지 않도록 노선 다양성을 반영했습니다.")
    st.dataframe(
        recommendation_df,
        use_container_width=True,
        hide_index=True,
    )

    top_item = recommendations[0]
    top_color = get_risk_color(top_item["risk_level"])

    st.markdown(
        f"""
        <div style="
            border-radius: 18px;
            padding: 28px;
            background-color: #FFFFFF;
            border: 1px solid #E5E7EB;
            margin-top: 28px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        ">
            <div style="font-size: 15px; color: #6B7280; margin-bottom: 8px;">
                1순위 추천
            </div>
            <div style="font-size: 30px; font-weight: 800; color: #111827; margin-bottom: 10px;">
                {display_airport(top_item["departure_airport"])} → {display_airport(top_item["arrival_airport"])}
            </div>
            <div style="font-size: 18px; color: #374151; margin-bottom: 8px;">
                추천 일정: {top_item["departure_date"]} ~ {top_item["return_date"]}
            </div>
            <div style="font-size: 18px; color: #374151; margin-bottom: 18px;">
                위험도: <span style="font-weight: 800; color: {top_color};">{top_item["risk_level"]}</span>
                · {top_item["risk_score"]}점
            </div>
            <div style="font-size: 26px; font-weight: 800; color: {top_color};">
                {top_item["purchase_timing_recommendation"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("1순위 추천에 대한 AI 2차 검토 보기", expanded=False):
        if top_ai_report:
            st.markdown(top_ai_report)
        else:
            st.warning("AI 2차 검토 결과가 비어 있습니다.")

        st.markdown("### 1순위 추천 사용 피처")

        matched_feature = top_item.get("matched_feature", {})

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


def render_analysis_result(risk_result, matched_feature, arrival_date, ai_report):
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
        <div class="result-fade-in">
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

        st.markdown("### AI 2차 검토")

        if ai_report:
            st.markdown(ai_report)
        else:
            st.warning("AI 설명이 비어 있습니다. 다시 분석을 실행해주세요.")

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


def clear_manual_result():
    st.session_state["analysis_result"] = None
    st.session_state["matched_feature"] = None
    st.session_state["arrival_date"] = None
    st.session_state["ai_report"] = None


def clear_text_result():
    st.session_state["parsed_request"] = None
    st.session_state["natural_recommendations"] = None
    st.session_state["top_ai_report"] = None


inject_global_style()

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

if "ai_report" not in st.session_state:
    st.session_state["ai_report"] = None

if "last_selected_key" not in st.session_state:
    st.session_state["last_selected_key"] = None

if "parsed_request" not in st.session_state:
    st.session_state["parsed_request"] = None

if "natural_recommendations" not in st.session_state:
    st.session_state["natural_recommendations"] = None

if "top_ai_report" not in st.session_state:
    st.session_state["top_ai_report"] = None

if "last_input_mode" not in st.session_state:
    st.session_state["last_input_mode"] = None


has_manual_result = st.session_state["analysis_result"] is not None
has_text_result = (
    st.session_state["parsed_request"] is not None
    and st.session_state["natural_recommendations"] is not None
)


if has_manual_result:
    render_analysis_result(
        st.session_state["analysis_result"],
        st.session_state["matched_feature"],
        st.session_state["arrival_date"],
        st.session_state["ai_report"],
    )

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    if st.button("다시 추천받기", type="primary", use_container_width=True):
        clear_manual_result()
        st.session_state["last_selected_key"] = None
        st.rerun()


elif has_text_result:
    render_natural_recommendations(
        parsed_request=st.session_state["parsed_request"],
        recommendations=st.session_state["natural_recommendations"],
        top_ai_report=st.session_state["top_ai_report"],
    )

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    if st.button("다시 추천받기", type="primary", use_container_width=True):
        clear_text_result()
        st.rerun()


else:
    st.markdown("### 분석 조건 입력")

    with st.container(border=True):
        input_mode = st.radio(
            "입력 방식 선택",
            ["날짜 직접 선택", "텍스트로 입력"],
            horizontal=True,
        )

        if (
            st.session_state["last_input_mode"] is not None
            and st.session_state["last_input_mode"] != input_mode
        ):
            clear_manual_result()
            clear_text_result()

        st.session_state["last_input_mode"] = input_mode

        if input_mode == "날짜 직접 선택":
            departure_airports = sorted(sample_df["departure_airport"].dropna().unique().tolist())
            available_years = sorted(sample_df["year"].dropna().astype(int).unique().tolist())

            default_departure_index = departure_airports.index("ICN") if "ICN" in departure_airports else 0

            col1, col2 = st.columns(2)

            with col1:
                departure_airport = st.selectbox(
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

            with col2:
                arrival_airport = st.selectbox(
                    "도착지",
                    arrival_candidates,
                    format_func=display_airport,
                )

            today_date = pd.Timestamp.today().date()

            date_col1, date_col2 = st.columns(2)

            with date_col1:
                departure_date = st.date_input(
                    "출발 예정일",
                    value=today_date + timedelta(days=30),
                )

            with date_col2:
                arrival_date = st.date_input(
                    "도착 예정일",
                    value=departure_date + timedelta(days=3),
                )

            if arrival_date < departure_date:
                st.error("도착 예정일은 출발 예정일 이후여야 합니다.")

            analysis_year = select_analysis_year(available_years, departure_date)

            current_selected_key = f"{departure_airport}|{arrival_airport}|{departure_date}|{arrival_date}"

            if (
                st.session_state["last_selected_key"] is not None
                and st.session_state["last_selected_key"] != current_selected_key
            ):
                clear_manual_result()

            button_col1, button_col2 = st.columns(2)

            with button_col1:
                run_button = st.button(
                    "분석 실행",
                    type="primary",
                    use_container_width=True,
                )

            with button_col2:
                reset_button = st.button(
                    "분석 초기화",
                    use_container_width=True,
                )

        else:
            st.markdown(
                """
                여행 가능 기간, 체류 기간, 목적지, 포함 조건을 문장으로 입력하면  
                AI가 필요한 조건을 추출해 추천 노선을 생성합니다.
                """
            )

            natural_text = st.text_area(
                "여행 조건 입력",
                value="",
                height=150,
                placeholder=(
                    "예: 내년 추석 일본여행 갈거야. 3박4일로 추천해줘.\n"
                    "예: 12월20일~12월30일 사이 4박5일로 일본여행 가고 싶어. 크리스마스는 포함됐으면 좋겠어."
                ),
            )

            button_col1, button_col2 = st.columns(2)

            with button_col1:
                natural_run_button = st.button(
                    "텍스트 조건으로 추천받기",
                    type="primary",
                    use_container_width=True,
                )

            with button_col2:
                natural_reset_button = st.button(
                    "추천 초기화",
                    use_container_width=True,
                )


    if input_mode == "날짜 직접 선택":
        if reset_button:
            clear_manual_result()
            st.session_state["last_selected_key"] = None
            st.rerun()

        if run_button:
            if arrival_date < departure_date:
                st.error("도착 예정일은 출발 예정일 이후여야 합니다.")
            else:
                loading_placeholder = st.empty()

                try:
                    loading_placeholder.markdown(
                        render_loading_overlay("FastAPI 백엔드에 분석 요청을 보내고 있습니다."),
                        unsafe_allow_html=True,
                    )
                    time.sleep(0.25)

                    api_response = analyze_route_via_api(
                        departure_airport=departure_airport,
                        arrival_airport=arrival_airport,
                        departure_date=str(departure_date),
                        arrival_date=str(arrival_date),
                        year=analysis_year,
                    )

                    loading_placeholder.markdown(
                        render_loading_overlay("백엔드 분석 결과를 화면에 표시할 준비를 하고 있습니다."),
                        unsafe_allow_html=True,
                    )
                    time.sleep(0.25)

                    st.session_state["analysis_result"] = api_response["risk_result"]
                    st.session_state["matched_feature"] = api_response["matched_feature"]
                    st.session_state["arrival_date"] = str(arrival_date)
                    st.session_state["ai_report"] = api_response["ai_report"]
                    st.session_state["last_selected_key"] = current_selected_key

                    loading_placeholder.empty()
                    st.rerun()

                except Exception as e:
                    loading_placeholder.empty()
                    st.error("분석 실행 중 오류가 발생했습니다.")
                    st.exception(e)

        st.markdown("### 항공권 구매 타이밍을 확인해보세요")

        st.markdown(
            """
            위 입력 박스에서 **출발지, 도착지, 출발 예정일, 도착 예정일**을 선택한 뒤  
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
                "API 기반 분석",
                "FastAPI 백엔드가 위험도와 구매 타이밍을 분석합니다.",
            )

        st.markdown("<div style='height: 44px;'></div>", unsafe_allow_html=True)

        render_buy_now_recommendations(sample_df)


    else:
        if natural_reset_button:
            clear_text_result()
            st.rerun()

        if natural_run_button:
            if not natural_text.strip():
                st.error("여행 조건을 입력해주세요.")
            else:
                loading_placeholder = st.empty()

                try:
                    loading_placeholder.markdown(
                        render_loading_overlay("FastAPI 백엔드에 텍스트 추천 요청을 보내고 있습니다."),
                        unsafe_allow_html=True,
                    )

                    api_response = recommend_text_via_api(
                        text=natural_text,
                        recommendation_count=5,
                    )

                    loading_placeholder.markdown(
                        render_loading_overlay("추천 결과 화면을 준비하고 있습니다."),
                        unsafe_allow_html=True,
                    )
                    time.sleep(0.25)

                    st.session_state["parsed_request"] = api_response["parsed_request"]
                    st.session_state["natural_recommendations"] = api_response["recommendations"]
                    st.session_state["top_ai_report"] = api_response["top_ai_report"]

                    loading_placeholder.empty()
                    st.rerun()

                except Exception as e:
                    loading_placeholder.empty()
                    st.error("텍스트 추천 실행 중 오류가 발생했습니다.")
                    st.exception(e)

        st.markdown("<div style='height: 34px;'></div>", unsafe_allow_html=True)

        guide_col1, guide_col2, guide_col3 = st.columns(3)

        with guide_col1:
            render_metric_card(
                "1단계",
                "텍스트 입력",
                "휴가 기간과 여행 조건을 문장으로 입력합니다.",
            )

        with guide_col2:
            render_metric_card(
                "2단계",
                "API 요청",
                "Streamlit 화면이 FastAPI 백엔드에 분석을 요청합니다.",
            )

        with guide_col3:
            render_metric_card(
                "3단계",
                "추천 결과 확인",
                "백엔드 응답 결과를 화면에서 확인합니다.",
            )


st.markdown("---")

with st.expander("분석 기준 보기", expanded=False):
    st.markdown(
        """
- 직접 선택 모드: 사용자가 출발지, 도착지, 출발일, 도착일을 직접 입력합니다.
- 텍스트 입력 모드: AI가 사용자의 문장에서 여행 조건을 추출합니다.
- 백엔드 처리: Streamlit 화면은 FastAPI API에 분석 요청을 보내고, FastAPI가 위험도 분석 결과를 JSON으로 반환합니다.
- 포함 조건: 크리스마스, 추석, 설날 등 사용자가 언급한 특정 날짜·공휴일이 여행 기간 안에 포함되도록 일정 후보를 필터링합니다.
- 항공 수요: 노선별 여객 증가율
- 운항 공급: 노선별 운항편 증가율
- 수요-공급 불균형: 여객 증가율과 운항편 증가율의 차이
- 노선 경쟁도: 항공사 수 및 LCC 비중
- 일정 요인: 공휴일 및 연휴 변수
- 환율: JPY/KRW 변동률, 낮은 가중치
- 결과: 가격 상승 위험도와 구매 타이밍 판단
"""
    )