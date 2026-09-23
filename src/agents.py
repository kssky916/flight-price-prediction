from datetime import datetime
from typing import Dict, Any, Optional


MAX_SCORE = 100

WEIGHTS = {
    "demand_pressure": 35,
    "supply_constraint": 25,
    "competition_pressure": 20,
    "schedule_pressure": 15,
    "exchange_pressure": 5,
}

LEGACY_SCORE_COLUMNS = [
    "demand_pressure_score",
    "supply_pressure_score",
    "exchange_pressure_score",
    "competition_pressure_score",
    "holiday_pressure_score",
]


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        value = float(value)

        if value != value:
            return default

        if value in [float("inf"), float("-inf")]:
            return default

        return value

    except Exception:
        return default


def _clip(value, min_value=0.0, max_value=1.0):
    value = _safe_float(value, 0.0)
    return max(min_value, min(max_value, value))


def _remove_legacy_score_columns(sample_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in sample_input.items()
        if key not in LEGACY_SCORE_COLUMNS
    }


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")

    except Exception:
        return None


def _as_list(value: Any):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return list(value)

    return [value]


def _count_required_dates_in_trip(
    departure_date: Any,
    return_date: Any,
    required_dates: Any,
) -> int:
    start_date = _parse_date(departure_date)
    end_date = _parse_date(return_date)

    if start_date is None:
        return 0

    if end_date is None:
        end_date = start_date

    if end_date < start_date:
        end_date = start_date

    count = 0

    for value in _as_list(required_dates):
        parsed_required_date = _parse_date(value)

        if parsed_required_date and start_date <= parsed_required_date <= end_date:
            count += 1

    return count


def calculate_schedule_pressure(sample_input: Dict[str, Any]) -> float:
    """
    사용자 여행일 기준 일정 압력.

    기존 방식:
    - 공휴일이 하루라도 겹치면 15점 전체 반영

    개선 방식:
    - 공휴일 포함 일수 / 전체 필수 공휴일 일수 비율로 반영
    - 예: 추석 3일 중 1일 포함 → 1/3 * 15점
    - 예: 추석 3일 중 3일 포함 → 3/3 * 15점
    """

    required_dates = (
        sample_input.get("required_include_dates")
        or sample_input.get("must_include_dates")
        or []
    )

    departure_date = sample_input.get("departure_date")
    return_date = sample_input.get("return_date") or sample_input.get("arrival_date")

    required_dates = _as_list(required_dates)

    if required_dates:
        matched_count = _count_required_dates_in_trip(
            departure_date=departure_date,
            return_date=return_date,
            required_dates=required_dates,
        )

        total_required_count = len(required_dates)

        if total_required_count <= 0:
            return 0.0

        return _clip(matched_count / total_required_count, 0.0, 1.0)

    holiday_count = _safe_float(sample_input.get("holiday_count"), 0.0)
    holiday_name = str(sample_input.get("holiday_name") or "").strip()
    must_include_holiday_names = sample_input.get("must_include_holiday_names") or []

    if holiday_count > 0:
        return 1.0

    if must_include_holiday_names:
        return 1.0

    if holiday_name and holiday_name.lower() not in ["nan", "none", ""]:
        return 1.0

    return 0.0


def calculate_factor_scores(sample_input: Dict[str, Any]) -> Dict[str, float]:
    demand_pressure = _clip(
        sample_input.get("normalized_demand_pressure"),
        0.0,
        1.0,
    )
    supply_constraint = _clip(
        sample_input.get("normalized_supply_constraint"),
        0.0,
        1.0,
    )
    competition_pressure = _clip(
        sample_input.get("normalized_competition_pressure"),
        0.0,
        1.0,
    )
    exchange_pressure = _clip(
        sample_input.get("normalized_exchange_pressure"),
        0.0,
        1.0,
    )
    schedule_pressure = calculate_schedule_pressure(sample_input)

    return {
        "demand_pressure_score": round(
            demand_pressure * WEIGHTS["demand_pressure"],
            1,
        ),
        "supply_constraint_score": round(
            supply_constraint * WEIGHTS["supply_constraint"],
            1,
        ),
        "competition_pressure_score": round(
            competition_pressure * WEIGHTS["competition_pressure"],
            1,
        ),
        "schedule_pressure_score": round(
            schedule_pressure * WEIGHTS["schedule_pressure"],
            1,
        ),
        "exchange_pressure_score": round(
            exchange_pressure * WEIGHTS["exchange_pressure"],
            1,
        ),
    }


def calculate_risk_score(factor_scores: Dict[str, float]) -> float:
    return round(sum(factor_scores.values()), 1)


def classify_risk_level(risk_score: float) -> str:
    if risk_score >= 60:
        return "높음"

    if risk_score >= 40:
        return "중간"

    return "낮음"


def recommend_purchase_timing(risk_level: str) -> str:
    if risk_level == "높음":
        return "빠른 구매 검토"

    if risk_level == "중간":
        return "가격 모니터링 후 구매"

    return "대기 가능"


def build_decision_reason(
    risk_score: float,
    risk_level: str,
    factor_scores: Dict[str, float],
) -> str:
    sorted_factors = sorted(
        factor_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    top_factors = [
        name
        for name, score in sorted_factors
        if score > 0
    ][:3]

    factor_name_map = {
        "demand_pressure_score": "수요 압력",
        "supply_constraint_score": "공급 제약",
        "competition_pressure_score": "경쟁도 압력",
        "schedule_pressure_score": "일정/공휴일 압력",
        "exchange_pressure_score": "환율 압력",
    }

    readable_factors = [
        factor_name_map.get(name, name)
        for name in top_factors
    ]

    if readable_factors:
        factor_text = ", ".join(readable_factors)
    else:
        factor_text = "주요 압력 요인 없음"

    return (
        f"정규화 기반 가격 상승 압력 점수는 {risk_score}점이며, "
        f"위험도는 '{risk_level}'입니다. "
        f"주요 영향 요인은 {factor_text}입니다."
    )


def run_agent_pipeline(sample_input: Dict[str, Any]) -> Dict[str, Any]:
    clean_input = _remove_legacy_score_columns(sample_input)

    factor_scores = calculate_factor_scores(clean_input)
    risk_score = calculate_risk_score(factor_scores)
    risk_level = classify_risk_level(risk_score)
    purchase_timing_recommendation = recommend_purchase_timing(risk_level)

    decision_reason = build_decision_reason(
        risk_score=risk_score,
        risk_level=risk_level,
        factor_scores=factor_scores,
    )

    result = {
        **clean_input,
        "risk_score": risk_score,
        "max_score": MAX_SCORE,
        "risk_level": risk_level,
        "purchase_timing_recommendation": purchase_timing_recommendation,
        "decision_reason": decision_reason,
        "factor_scores": factor_scores,
        "risk_method": "normalized_percentile_based_pressure_score",
        "risk_score_description": (
            "실제 항공권 가격 예측값이 아니라, 연도별 노선 분포 기준으로 정규화한 "
            "수요·공급·경쟁도·일정·환율 기반 가격 상승 압력 지표입니다. "
            "일정/공휴일 압력은 여행 기간에 포함된 주요 공휴일 일수 비율을 기준으로 반영합니다."
        ),
    }

    return result