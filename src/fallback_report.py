from typing import Dict, Any, List


def get_top_reasons(risk_result: Dict[str, Any]) -> List[str]:
    factors = risk_result["factor_analysis"]

    sorted_factors = sorted(
        factors.values(),
        key=lambda item: item["score"],
        reverse=True
    )

    reasons = []

    for factor in sorted_factors:
        if factor["score"] >= 3:
            reasons.append(
                f"{factor['factor_name']}: {factor['business_interpretation']}"
            )

    if not reasons:
        reasons.append("현재 조건에서는 강한 가격 상승 위험 요인이 크게 확인되지 않았습니다.")

    return reasons[:3]


def build_fallback_report(
    risk_result: Dict[str, Any],
    error_message: str | None = None
) -> Dict[str, Any]:
    risk = risk_result["risk_assessment"]
    route = risk_result["user_query"]["route_name"]
    departure_date = risk_result["user_query"]["departure_date"]

    if risk["risk_level"] == "높음":
        headline = "구매를 오래 미루기에는 위험 요인이 많은 조건입니다."
        action_guide = "일정이 고정되어 있다면 현재 가격을 확인하고 빠른 구매를 검토하는 것이 좋습니다."
    elif risk["risk_level"] == "보통":
        headline = "며칠 더 가격 변동을 확인해볼 수 있는 조건입니다."
        action_guide = "바로 구매를 확정하기보다 며칠간 가격 변동을 확인하면서 판단하는 것이 적절합니다."
    else:
        headline = "현재 조건에서는 비교적 여유가 있는 편입니다."
        action_guide = "일정에 여유가 있다면 다른 날짜나 목적지와 비교한 뒤 구매를 결정할 수 있습니다."

    caution = (
        "이 결과는 실제 항공권 판매 가격, 잔여 좌석 수, 예약률을 예측한 것이 아니라 "
        "공공데이터 기반 요인을 활용한 구매 지연 위험도 판단입니다."
    )

    if error_message:
        caution += f"\n\nLLM 응답 생성 실패로 규칙 기반 리포트를 사용했습니다. 오류: {error_message}"

    return {
        "headline": headline,
        "one_line_summary": f"{route} {departure_date} 출발 항공권은 {risk['recommendation']}가 필요한 상황입니다.",
        "main_reasons": get_top_reasons(risk_result),
        "action_guide": action_guide,
        "alternative_suggestion": "날짜 변경 What-if와 목적지 비교 결과를 함께 확인해 더 낮은 위험도의 선택지를 검토할 수 있습니다.",
        "caution": caution,
        "display_level": risk["risk_level"],
    }


def format_report_markdown(report: Dict[str, Any]) -> str:
    reasons = "\n".join([
        f"- {reason}" for reason in report.get("main_reasons", [])
    ])

    return f"""
### {report["headline"]}

{report["one_line_summary"]}

#### 주요 판단 근거
{reasons}

#### 구매 판단 가이드
{report["action_guide"]}

#### 대안 검토
{report["alternative_suggestion"]}

#### 유의사항
{report["caution"]}
""".strip()