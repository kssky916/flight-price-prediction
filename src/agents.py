from typing import Dict, Any, List
from src.validators import validate_agent_input


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        value = str(value).replace(",", "").strip()

        if value == "" or value.lower() == "nan":
            return default

        return float(value)
    except Exception:
        return default


def safe_str(value, default: str = "") -> str:
    if value is None:
        return default

    value = str(value).strip()

    if value.lower() == "nan":
        return default

    return value


def score_demand(passenger_growth_rate: float) -> Dict[str, Any]:
    """
    수요 압력 점수.
    여객 증가율이 높을수록 가격 상승 위험이 높다고 판단.
    """
    if passenger_growth_rate >= 30:
        score = 5
        reason = "여객 증가율이 30% 이상으로 수요 압력이 매우 높습니다."
    elif passenger_growth_rate >= 15:
        score = 4
        reason = "여객 증가율이 15% 이상으로 수요 증가세가 뚜렷합니다."
    elif passenger_growth_rate >= 5:
        score = 3
        reason = "여객 증가율이 5% 이상으로 완만한 수요 증가가 있습니다."
    elif passenger_growth_rate >= 0:
        score = 2
        reason = "여객 수요가 전년 대비 소폭 증가 또는 유지 수준입니다."
    else:
        score = 1
        reason = "여객 수요가 전년 대비 감소하여 수요 압력이 낮습니다."

    return {
        "factor": "demand",
        "score": score,
        "value": passenger_growth_rate,
        "reason": reason,
    }


def score_supply(flight_growth_rate: float) -> Dict[str, Any]:
    """
    공급 압력 점수.
    운항편 증가율이 낮거나 감소할수록 공급 부족 위험이 높다고 판단.
    """
    if flight_growth_rate <= -10:
        score = 5
        reason = "운항편 수가 10% 이상 감소하여 공급 축소 압력이 큽니다."
    elif flight_growth_rate <= 0:
        score = 4
        reason = "운항편 수가 전년 대비 감소 또는 정체되어 공급 여력이 제한적입니다."
    elif flight_growth_rate <= 10:
        score = 3
        reason = "운항편 수 증가율이 10% 이하로 수요 증가를 충분히 따라가지 못할 수 있습니다."
    elif flight_growth_rate <= 25:
        score = 2
        reason = "운항편 수가 일정 수준 증가해 공급 부담은 보통 수준입니다."
    else:
        score = 1
        reason = "운항편 수 증가율이 높아 공급 확대 여력이 있습니다."

    return {
        "factor": "supply",
        "score": score,
        "value": flight_growth_rate,
        "reason": reason,
    }


def score_exchange(jpy_krw_change_rate: float) -> Dict[str, Any]:
    """
    환율 압력 점수.
    JPY/KRW 상승률이 높을수록 일본 여행 비용 부담이 커진다고 판단.
    """
    if jpy_krw_change_rate >= 3:
        score = 5
        reason = "JPY/KRW 환율 상승률이 3% 이상으로 여행 비용 부담이 커질 수 있습니다."
    elif jpy_krw_change_rate >= 1.5:
        score = 4
        reason = "JPY/KRW 환율이 상승세를 보여 비용 부담 요인이 있습니다."
    elif jpy_krw_change_rate >= 0:
        score = 3
        reason = "JPY/KRW 환율이 소폭 상승 또는 유지 수준입니다."
    elif jpy_krw_change_rate >= -2:
        score = 2
        reason = "JPY/KRW 환율이 소폭 하락하여 비용 부담은 제한적입니다."
    else:
        score = 1
        reason = "JPY/KRW 환율이 하락해 환율 측면의 부담은 낮습니다."

    return {
        "factor": "exchange",
        "score": score,
        "value": jpy_krw_change_rate,
        "reason": reason,
    }


def score_competition(avg_carrier_count: float, avg_lcc_share: float) -> Dict[str, Any]:
    """
    경쟁 압력 점수.
    항공사 수가 적을수록 경쟁이 약하고 가격 상승 위험이 높다고 판단.
    LCC 비중이 높으면 일부 완화.
    """
    if avg_carrier_count <= 2:
        base_score = 5
        reason = "운항 항공사 수가 적어 노선 경쟁도가 낮습니다."
    elif avg_carrier_count <= 4:
        base_score = 4
        reason = "운항 항공사 수가 제한적이어서 경쟁 압력이 크지 않습니다."
    elif avg_carrier_count <= 6:
        base_score = 3
        reason = "운항 항공사 수가 보통 수준입니다."
    elif avg_carrier_count <= 8:
        base_score = 2
        reason = "운항 항공사 수가 비교적 많아 경쟁 완화 요인이 있습니다."
    else:
        base_score = 1
        reason = "운항 항공사 수가 많아 경쟁 압력이 충분합니다."

    if avg_lcc_share >= 0.5 and base_score > 1:
        score = base_score - 1
        reason += " 다만 LCC 비중이 높아 가격 상승 압력은 일부 완화됩니다."
    else:
        score = base_score

    return {
        "factor": "competition",
        "score": score,
        "carrier_count": avg_carrier_count,
        "lcc_share": avg_lcc_share,
        "reason": reason,
    }


def score_holiday(days_to_holiday: float, holiday_count: float, holiday_name: str) -> Dict[str, Any]:
    """
    공휴일 압력 점수.
    실제 출발일과 공휴일 간 거리가 있으면 days_to_holiday 기준.
    없으면 연도별 공휴일 수를 보조 기준으로 사용.
    """
    holiday_name = safe_str(holiday_name)

    if holiday_name and days_to_holiday > 0:
        if days_to_holiday <= 7:
            score = 5
            reason = f"출발일이 공휴일 또는 연휴와 7일 이내로 가깝습니다. 관련 공휴일: {holiday_name}"
        elif days_to_holiday <= 14:
            score = 4
            reason = f"출발일이 공휴일 또는 연휴와 14일 이내입니다. 관련 공휴일: {holiday_name}"
        elif days_to_holiday <= 30:
            score = 3
            reason = f"출발일이 공휴일과 한 달 이내입니다. 관련 공휴일: {holiday_name}"
        else:
            score = 2
            reason = "출발일과 공휴일 간 거리가 있어 연휴 영향은 제한적입니다."
    else:
        if holiday_count >= 15:
            score = 3
            reason = "해당 연도 공휴일 수가 많아 여행 수요 보조 요인이 있습니다."
        elif holiday_count >= 10:
            score = 2
            reason = "해당 연도 공휴일 수가 보통 수준입니다."
        else:
            score = 1
            reason = "공휴일 요인으로 인한 추가 수요 압력은 낮습니다."

    return {
        "factor": "holiday",
        "score": score,
        "days_to_holiday": days_to_holiday,
        "holiday_count": holiday_count,
        "holiday_name": holiday_name,
        "reason": reason,
    }


def classify_risk(total_score: int) -> Dict[str, str]:
    if total_score >= 18:
        return {
            "risk_level": "높음",
            "purchase_timing_recommendation": "빠른 구매 검토",
            "decision_reason": "수요·공급·환율·경쟁도 중 여러 요인에서 가격 상승 위험이 높게 나타났습니다.",
        }

    if total_score >= 12:
        return {
            "risk_level": "중간",
            "purchase_timing_recommendation": "가격 모니터링 후 구매",
            "decision_reason": "일부 가격 상승 요인이 있으나, 모든 지표가 강한 위험 신호를 보이는 것은 아닙니다.",
        }

    return {
        "risk_level": "낮음",
        "purchase_timing_recommendation": "대기 가능",
        "decision_reason": "현재 데이터 기준 가격 상승 압력이 낮거나 제한적입니다.",
    }


def build_evidence(data: Dict[str, Any], factor_results: List[Dict[str, Any]]) -> List[str]:
    evidence = []

    evidence.append(
        f"노선: {safe_str(data.get('departure_airport'))} → {safe_str(data.get('arrival_airport'))}"
    )

    evidence.append(
        f"출발일: {safe_str(data.get('departure_date'))}"
    )

    evidence.append(
        f"여객 증가율: {safe_float(data.get('passenger_growth_rate')):.2f}%"
    )

    evidence.append(
        f"운항편 증가율: {safe_float(data.get('flight_growth_rate')):.2f}%"
    )

    if "avg_carrier_count" in data:
        evidence.append(
            f"평균 운항 항공사 수: {safe_float(data.get('avg_carrier_count')):.2f}개"
        )

    if "avg_lcc_share" in data:
        evidence.append(
            f"LCC 비중: {safe_float(data.get('avg_lcc_share')):.2f}"
        )

    evidence.append(
        f"JPY/KRW 30일 변동률: {safe_float(data.get('jpy_krw_change_rate')):.2f}%"
    )

    if "holiday_count" in data:
        evidence.append(
            f"연도별 공휴일 수: {safe_float(data.get('holiday_count')):.0f}일"
        )

    for item in factor_results:
        evidence.append(item["reason"])

    return evidence


def run_agent_pipeline(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    공공데이터 기반 항공권 가격 상승 위험도 및 구매 타이밍 판단.
    실제 항공권 가격 금액을 예측하지 않는다.
    """
    validate_agent_input(data)

    passenger_growth_rate = safe_float(data.get("passenger_growth_rate"))
    flight_growth_rate = safe_float(data.get("flight_growth_rate"))
    jpy_krw_change_rate = safe_float(data.get("jpy_krw_change_rate"))

    avg_carrier_count = safe_float(data.get("avg_carrier_count", data.get("carrier_count", 0)))
    avg_lcc_share = safe_float(data.get("avg_lcc_share", data.get("lcc_share", 0)))

    days_to_holiday = safe_float(data.get("days_to_holiday", 0))
    holiday_count = safe_float(data.get("holiday_count", 0))
    holiday_name = safe_str(data.get("holiday_name", data.get("holiday_names", "")))

    demand_result = score_demand(passenger_growth_rate)
    supply_result = score_supply(flight_growth_rate)
    exchange_result = score_exchange(jpy_krw_change_rate)
    competition_result = score_competition(avg_carrier_count, avg_lcc_share)
    holiday_result = score_holiday(days_to_holiday, holiday_count, holiday_name)

    factor_results = [
        demand_result,
        supply_result,
        exchange_result,
        competition_result,
        holiday_result,
    ]

    total_score = sum(item["score"] for item in factor_results)
    decision = classify_risk(total_score)

    evidence = build_evidence(data, factor_results)

    result = {
        "departure_airport": data.get("departure_airport"),
        "arrival_airport": data.get("arrival_airport"),
        "departure_date": data.get("departure_date"),
        "route": data.get("route", f"{data.get('departure_airport')}-{data.get('arrival_airport')}"),
        "risk_score": total_score,
        "max_score": 25,
        "risk_level": decision["risk_level"],
        "purchase_timing_recommendation": decision["purchase_timing_recommendation"],
        "decision_reason": decision["decision_reason"],
        "factor_scores": {
            "demand_pressure_score": demand_result["score"],
            "supply_pressure_score": supply_result["score"],
            "exchange_pressure_score": exchange_result["score"],
            "competition_pressure_score": competition_result["score"],
            "holiday_pressure_score": holiday_result["score"],
        },
        "factor_details": factor_results,
        "evidence": evidence,
        "summary": (
            f"현재 데이터 기준 가격 상승 위험도는 '{decision['risk_level']}'입니다. "
            f"권장 구매 타이밍은 '{decision['purchase_timing_recommendation']}'입니다."
        ),
        "caution": (
            "이 결과는 실제 항공권 가격 금액 예측이 아니라, 공공데이터 기반 가격 상승 위험도와 "
            "구매 타이밍 판단 결과입니다."
        ),
    }

    return result