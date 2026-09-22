from typing import Dict, Any, List


def _get_value(data: Dict[str, Any], key: str, default=""):
    value = data.get(key, default)

    if value is None:
        return default

    return value


def build_grounded_explanation(risk_result: Dict[str, Any]) -> str:
    risk_level = _get_value(risk_result, "risk_level")
    recommendation = _get_value(risk_result, "purchase_timing_recommendation")
    risk_score = _get_value(risk_result, "risk_score")
    max_score = _get_value(risk_result, "max_score", 25)
    decision_reason = _get_value(risk_result, "decision_reason")
    caution = _get_value(risk_result, "caution")

    factor_details: List[Dict[str, Any]] = risk_result.get("factor_details", [])
    evidence: List[str] = risk_result.get("evidence", [])

    lines = []

    lines.append("## 항공권 가격 상승 위험도 분석 결과")
    lines.append("")
    lines.append(f"- 위험도: **{risk_level}**")
    lines.append(f"- 위험도 점수: **{risk_score} / {max_score}**")
    lines.append(f"- 구매 타이밍 판단: **{recommendation}**")
    lines.append("")
    lines.append("### 판단 근거")
    lines.append(decision_reason)
    lines.append("")

    if factor_details:
        lines.append("### 요인별 분석")
        for item in factor_details:
            factor = item.get("factor", "")
            score = item.get("score", "")
            reason = item.get("reason", "")

            factor_name = {
                "demand": "수요",
                "supply": "공급",
                "exchange": "환율",
                "competition": "경쟁도",
                "holiday": "공휴일/연휴",
            }.get(factor, factor)

            lines.append(f"- {factor_name}: {score}점 — {reason}")

        lines.append("")

    if evidence:
        lines.append("### 사용된 데이터 근거")
        for item in evidence[:12]:
            lines.append(f"- {item}")

        lines.append("")

    lines.append("### 해석 시 주의사항")
    lines.append(caution)
    lines.append("")
    lines.append(
        "이 서비스는 실제 항공권 가격을 금액으로 예측하지 않고, "
        "수요·공급·환율·경쟁도·공휴일 데이터를 기반으로 가격 상승 가능성과 구매 타이밍을 판단합니다."
    )

    return "\n".join(lines)


def generate_report(risk_result: Dict[str, Any]) -> str:
    return build_grounded_explanation(risk_result)


def generate_llm_report(risk_result: Dict[str, Any]) -> str:
    return build_grounded_explanation(risk_result)


def generate_fallback_report(risk_result: Dict[str, Any]) -> str:
    return build_grounded_explanation(risk_result)


def generate_purchase_timing_report(risk_result: Dict[str, Any]) -> str:
    return build_grounded_explanation(risk_result)


def build_report(risk_result: Dict[str, Any]) -> str:
    return build_grounded_explanation(risk_result)