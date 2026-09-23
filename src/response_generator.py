from typing import Dict, Any, List

from src.llm_client import is_llm_available, generate_llm_explanation


def _get_value(data: Dict[str, Any], key: str, default=""):
    value = data.get(key, default)
    if value is None:
        return default
    return value


def build_rule_based_explanation(risk_result: Dict[str, Any]) -> str:
    risk_level = _get_value(risk_result, "risk_level")
    recommendation = _get_value(risk_result, "purchase_timing_recommendation")
    risk_score = _get_value(risk_result, "risk_score")
    max_score = _get_value(risk_result, "max_score", 100)
    decision_reason = _get_value(risk_result, "decision_reason")

    factor_details: List[Dict[str, Any]] = risk_result.get("factor_details", [])
    evidence: List[str] = risk_result.get("evidence", [])

    lines = []
    lines.append("### 데이터 기반 구매 타이밍 설명")
    lines.append("")
    lines.append("#### 1. 현재 판단")
    lines.append(f"- 현재 가격 상승 위험도는 **{risk_level}**이며, 구매 판단은 **{recommendation}**입니다.")
    lines.append("")
    lines.append("#### 2. 주요 근거")

    if factor_details:
        sorted_factors = sorted(
            factor_details,
            key=lambda item: item.get("score", 0),
            reverse=True,
        )

        for item in sorted_factors[:3]:
            reason = item.get("reason", "")
            score = item.get("score", "")
            max_score_item = item.get("max_score", "")
            lines.append(f"- {reason} ({score}/{max_score_item}점)")
    else:
        lines.append(f"- {decision_reason}")

    lines.append("")
    lines.append("#### 3. 해석")
    lines.append(f"- 위험도 점수는 **{risk_score}/{max_score}점**입니다.")
    lines.append(f"- {decision_reason}")
    lines.append("")
    lines.append("#### 4. 사용 데이터")

    for item in evidence[:8]:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("#### 5. 최종 판단")
    lines.append(f"- 현재 조건에서는 **{recommendation}**이 적절합니다.")

    return "\n".join(lines)


def generate_purchase_timing_report(risk_result: Dict[str, Any]) -> str:
    if is_llm_available():
        try:
            return generate_llm_explanation(risk_result)
        except Exception as e:
            fallback = build_rule_based_explanation(risk_result)
            return (
                "### LLM 설명 생성 실패\n\n"
                f"- 오류: `{str(e)}`\n"
                "- 아래는 데이터 기반 기본 설명입니다.\n\n"
                f"{fallback}"
            )

    return build_rule_based_explanation(risk_result)


def generate_report(risk_result: Dict[str, Any]) -> str:
    return generate_purchase_timing_report(risk_result)


def generate_llm_report(risk_result: Dict[str, Any]) -> str:
    return generate_purchase_timing_report(risk_result)


def generate_fallback_report(risk_result: Dict[str, Any]) -> str:
    return build_rule_based_explanation(risk_result)


def build_report(risk_result: Dict[str, Any]) -> str:
    return generate_purchase_timing_report(risk_result)