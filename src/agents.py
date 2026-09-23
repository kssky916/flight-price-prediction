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


def score_demand_supply_gap(passenger_growth_rate: float, flight_growth_rate: float) -> Dict[str, Any]:
    """
    수요-공급 불균형 점수.
    단순히 여객이 전년 대비 증가했다는 이유만으로 수요가 강하다고 보지 않는다.
    핵심은 여객 증가율이 운항편 증가율보다 얼마나 빠른지이다.
    """
    gap = passenger_growth_rate - flight_growth_rate

    if gap >= 30:
        score = 35
        reason = (
            "여객 증가율이 운항편 증가율보다 30%p 이상 높아 "
            "수요가 공급 확대 속도보다 빠르게 증가한 것으로 판단됩니다."
        )
    elif gap >= 15:
        score = 28
        reason = (
            "여객 증가율이 운항편 증가율보다 15%p 이상 높아 "
            "수요-공급 불균형 가능성이 있습니다."
        )
    elif gap >= 5:
        score = 20
        reason = (
            "여객 증가율이 운항편 증가율보다 소폭 높아 "
            "일부 수요 압력이 존재합니다."
        )
    elif gap >= -5:
        score = 12
        reason = (
            "여객 증가율과 운항편 증가율이 유사해 "
            "수요와 공급이 비교적 균형적인 상태로 판단됩니다."
        )
    else:
        score = 5
        reason = (
            "운항편 증가율이 여객 증가율보다 높아 "
            "공급 측면의 여유가 있는 것으로 판단됩니다."
        )

    return {
        "factor": "demand_supply_gap",
        "score": score,
        "max_score": 35,
        "passenger_growth_rate": passenger_growth_rate,
        "flight_growth_rate": flight_growth_rate,
        "gap": gap,
        "reason": reason,
    }


def score_supply(flight_growth_rate: float) -> Dict[str, Any]:
    """
    운항 공급 점수.
    운항편 수가 감소하거나 정체될수록 공급 부족 위험이 높다고 판단.
    """
    if flight_growth_rate <= -10:
        score = 25
        reason = "운항편 수가 10% 이상 감소하여 공급 축소 압력이 큽니다."
    elif flight_growth_rate <= 0:
        score = 20
        reason = "운항편 수가 전년 대비 감소 또는 정체되어 공급 여력이 제한적입니다."
    elif flight_growth_rate <= 10:
        score = 14
        reason = "운항편 수 증가율이 낮아 수요 증가를 충분히 흡수하지 못할 수 있습니다."
    elif flight_growth_rate <= 25:
        score = 8
        reason = "운항편 수가 일정 수준 증가하여 공급 부담은 보통 수준입니다."
    else:
        score = 3
        reason = "운항편 수 증가율이 높아 공급 확대 여력이 있습니다."

    return {
        "factor": "supply",
        "score": score,
        "max_score": 25,
        "value": flight_growth_rate,
        "reason": reason,
    }


def score_competition(avg_carrier_count: float, avg_lcc_share: float) -> Dict[str, Any]:
    """
    경쟁도 점수.
    운항 항공사 수가 적을수록 가격 상승 압력이 커질 수 있다.
    LCC 비중이 높으면 가격 상승 압력을 일부 완화한다.
    """
    if avg_carrier_count <= 2:
        base_score = 20
        reason = "운항 항공사 수가 적어 노선 경쟁도가 낮습니다."
    elif avg_carrier_count <= 4:
        base_score = 16
        reason = "운항 항공사 수가 제한적이어서 경쟁 압력이 크지 않습니다."
    elif avg_carrier_count <= 6:
        base_score = 11
        reason = "운항 항공사 수가 보통 수준입니다."
    elif avg_carrier_count <= 8:
        base_score = 7
        reason = "운항 항공사 수가 비교적 많아 경쟁 완화 요인이 있습니다."
    else:
        base_score = 3
        reason = "운항 항공사 수가 많아 경쟁 압력이 충분합니다."

    if avg_lcc_share >= 0.5:
        score = max(base_score - 4, 1)
        reason += " 또한 LCC 비중이 높아 가격 상승 압력은 일부 완화됩니다."
    elif avg_lcc_share >= 0.3:
        score = max(base_score - 2, 1)
        reason += " LCC 비중이 일부 존재해 경쟁 완화 요인이 있습니다."
    else:
        score = base_score

    return {
        "factor": "competition",
        "score": score,
        "max_score": 20,
        "carrier_count": avg_carrier_count,
        "lcc_share": avg_lcc_share,
        "reason": reason,
    }


def score_holiday(days_to_holiday: float, holiday_count: float, holiday_name: str) -> Dict[str, Any]:
    """
    공휴일/연휴 점수.
    출발일이 연휴와 가까울수록 여행 수요가 증가할 가능성을 반영.
    현재 MVP에서는 days_to_holiday가 없을 경우 연도별 공휴일 수를 보조 기준으로 사용.
    """
    holiday_name = safe_str(holiday_name)

    if holiday_name and days_to_holiday > 0:
        if days_to_holiday <= 7:
            score = 15
            reason = f"출발일이 공휴일 또는 연휴와 7일 이내로 가깝습니다. 관련 공휴일: {holiday_name}"
        elif days_to_holiday <= 14:
            score = 12
            reason = f"출발일이 공휴일 또는 연휴와 14일 이내입니다. 관련 공휴일: {holiday_name}"
        elif days_to_holiday <= 30:
            score = 8
            reason = f"출발일이 공휴일과 한 달 이내입니다. 관련 공휴일: {holiday_name}"
        else:
            score = 4
            reason = "출발일과 공휴일 간 거리가 있어 연휴 영향은 제한적입니다."
    else:
        if holiday_count >= 15:
            score = 10
            reason = "해당 연도 공휴일 수가 많아 여행 수요 보조 요인이 있습니다."
        elif holiday_count >= 10:
            score = 6
            reason = "해당 연도 공휴일 수가 보통 수준입니다."
        else:
            score = 3
            reason = "공휴일 요인으로 인한 추가 수요 압력은 낮습니다."

    return {
        "factor": "holiday",
        "score": score,
        "max_score": 15,
        "days_to_holiday": days_to_holiday,
        "holiday_count": holiday_count,
        "holiday_name": holiday_name,
        "reason": reason,
    }


def score_exchange(jpy_krw_change_rate: float) -> Dict[str, Any]:
    """
    환율 점수.
    환율은 항공권 가격 상승을 직접 결정하는 변수가 아니므로 낮은 가중치로 반영.
    """
    if jpy_krw_change_rate >= 5:
        score = 5
        reason = "JPY/KRW 환율 상승률이 높아 여행 비용 부담 요인으로 일부 반영됩니다."
    elif jpy_krw_change_rate >= 2:
        score = 4
        reason = "JPY/KRW 환율이 상승세이나 가격 상승 위험도에는 낮은 가중치로 반영됩니다."
    elif jpy_krw_change_rate >= 0:
        score = 3
        reason = "JPY/KRW 환율이 소폭 상승 또는 유지 수준입니다."
    elif jpy_krw_change_rate >= -3:
        score = 2
        reason = "JPY/KRW 환율이 소폭 하락하여 환율 부담은 제한적입니다."
    else:
        score = 1
        reason = "JPY/KRW 환율이 하락하여 환율 측면의 부담은 낮습니다."

    return {
        "factor": "exchange",
        "score": score,
        "max_score": 5,
        "value": jpy_krw_change_rate,
        "reason": reason,
    }


def classify_risk(total_score: int) -> Dict[str, str]:
    if total_score >= 70:
        return {
            "risk_level": "높음",
            "purchase_timing_recommendation": "빠른 구매 검토",
            "decision_reason": "수요-공급 불균형, 공급 제약, 경쟁도, 연휴 요인 중 여러 항목에서 가격 상승 위험 신호가 나타났습니다.",
        }

    if total_score >= 45:
        return {
            "risk_level": "중간",
            "purchase_timing_recommendation": "가격 모니터링 후 구매",
            "decision_reason": "일부 가격 상승 요인이 있으나, 모든 지표가 강한 위험 신호를 보이는 것은 아닙니다.",
        }

    return {
        "risk_level": "낮음",
        "purchase_timing_recommendation": "대기 가능",
        "decision_reason": "현재 데이터 기준 수요-공급 불균형과 경쟁도 측면의 가격 상승 압력이 제한적입니다.",
    }


def build_evidence(data: Dict[str, Any], factor_results: List[Dict[str, Any]]) -> List[str]:
    evidence = []

    passenger_growth_rate = safe_float(data.get("passenger_growth_rate"))
    flight_growth_rate = safe_float(data.get("flight_growth_rate"))
    gap = passenger_growth_rate - flight_growth_rate

    evidence.append(f"노선: {safe_str(data.get('departure_airport'))} → {safe_str(data.get('arrival_airport'))}")
    evidence.append(f"출발일: {safe_str(data.get('departure_date'))}")
    evidence.append(f"여객 증가율: {passenger_growth_rate:.2f}%")
    evidence.append(f"운항편 증가율: {flight_growth_rate:.2f}%")
    evidence.append(f"수요-공급 증가율 차이: {gap:.2f}%p")

    if "avg_carrier_count" in data:
        evidence.append(f"평균 운항 항공사 수: {safe_float(data.get('avg_carrier_count')):.2f}개")

    if "avg_lcc_share" in data:
        evidence.append(f"LCC 비중: {safe_float(data.get('avg_lcc_share')):.2f}")

    evidence.append(f"JPY/KRW 30일 변동률: {safe_float(data.get('jpy_krw_change_rate')):.2f}%")

    if "holiday_count" in data:
        evidence.append(f"연도별 공휴일 수: {safe_float(data.get('holiday_count')):.0f}일")

    for item in factor_results:
        evidence.append(item["reason"])

    return evidence


def run_agent_pipeline(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    공공데이터 기반 항공권 가격 상승 위험도 및 구매 타이밍 판단.
    핵심 기준은 단순 여객 증가율이 아니라 수요-공급 불균형이다.
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

    demand_supply_gap_result = score_demand_supply_gap(passenger_growth_rate, flight_growth_rate)
    supply_result = score_supply(flight_growth_rate)
    competition_result = score_competition(avg_carrier_count, avg_lcc_share)
    holiday_result = score_holiday(days_to_holiday, holiday_count, holiday_name)
    exchange_result = score_exchange(jpy_krw_change_rate)

    factor_results = [
        demand_supply_gap_result,
        supply_result,
        competition_result,
        holiday_result,
        exchange_result,
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
        "max_score": 100,
        "risk_level": decision["risk_level"],
        "purchase_timing_recommendation": decision["purchase_timing_recommendation"],
        "decision_reason": decision["decision_reason"],
        "factor_scores": {
            "demand_supply_gap_score": demand_supply_gap_result["score"],
            "supply_pressure_score": supply_result["score"],
            "competition_pressure_score": competition_result["score"],
            "holiday_pressure_score": holiday_result["score"],
            "exchange_pressure_score": exchange_result["score"],
        },
        "factor_details": factor_results,
        "evidence": evidence,
        "summary": (
            f"현재 데이터 기준 가격 상승 위험도는 '{decision['risk_level']}'입니다. "
            f"권장 구매 타이밍은 '{decision['purchase_timing_recommendation']}'입니다."
        ),
    }

    return result