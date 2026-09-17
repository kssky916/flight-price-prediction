from typing import Dict, Any


def _format_factor_reasons(risk_result: Dict[str, Any]) -> str:
    factors = risk_result["factor_analysis"]

    sorted_factors = sorted(
        factors.values(),
        key=lambda factor: factor["score"],
        reverse=True
    )

    lines = []

    for factor in sorted_factors:
        if factor["score"] >= 3:
            lines.append(
                f"- **{factor['factor_name']}**: {factor['business_interpretation']}"
            )

    if not lines:
        lines.append("- 현재 조건에서는 강한 가격 상승 위험 요인이 크게 확인되지 않았습니다.")

    return "\n".join(lines)


def generate_user_response(risk_result: Dict[str, Any]) -> str:
    user_query = risk_result["user_query"]
    risk = risk_result["risk_assessment"]

    route_name = user_query["route_name"]
    departure_date = user_query["departure_date"]

    if risk["risk_level"] == "높음":
        headline = "구매를 오래 미루기에는 위험 요인이 많은 조건입니다."
        action = "일정이 고정되어 있다면 현재 가격을 확인하고 빠른 구매를 검토하는 것이 좋습니다."
    elif risk["risk_level"] == "보통":
        headline = "며칠 더 가격 변동을 확인해볼 수 있는 조건입니다."
        action = "바로 구매를 확정하기보다는 며칠간 가격 변동을 확인하면서 판단하는 것이 적절합니다."
    else:
        headline = "현재 조건에서는 비교적 여유가 있는 편입니다."
        action = "일정에 여유가 있다면 다른 날짜나 목적지와 비교한 뒤 구매를 결정할 수 있습니다."

    factor_reasons = _format_factor_reasons(risk_result)

    return f"""
### {headline}

**{route_name} {departure_date} 출발 항공권**은 현재 기준으로 **{risk["recommendation"]}**가 필요한 상황입니다.

#### 주요 판단 근거
{factor_reasons}

#### 종합 판단
- 구매 지연 위험: **{risk["risk_level"]}**
- 종합 점수: **{risk["risk_score"]}/{risk["max_score"]}점**
- 판단 신뢰도: **{risk["confidence"]}**

#### 다음 행동 가이드
{action}

#### 유의사항
이 결과는 실제 항공권 판매 가격, 잔여 좌석 수, 예약률을 예측한 것이 아닙니다.  
공공데이터 기반 수요·공급·연휴·환율·운항 요인을 활용한 **구매 지연 위험도 판단 결과**입니다.
""".strip()