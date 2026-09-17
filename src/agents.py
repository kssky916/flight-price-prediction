from datetime import datetime
from typing import Dict, Any

from src.validators import validate_agent_input


def get_status_by_score(score: int) -> str:
    if score >= 4:
        return "위험"
    if score >= 2:
        return "주의"
    return "보통"


def build_agent_result(
    factor_name: str,
    status: str,
    score: int,
    evidence: str,
    interpretation: str,
    data_source: str,
    used_features: list,
    threshold: str,
    is_available: bool = True,
    max_score: int = 5
) -> Dict[str, Any]:
    return {
        "factor_name": factor_name,
        "status": status,
        "score": score,
        "max_score": max_score,
        "evidence": evidence,
        "business_interpretation": interpretation,
        "data_source": data_source,
        "used_features": used_features,
        "threshold": threshold,
        "is_available": is_available
    }


def demand_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    passenger_growth_rate = data.get("passenger_growth_rate")

    if passenger_growth_rate is None:
        return build_agent_result(
            factor_name="수요",
            status="정보 부족",
            score=0,
            evidence="여객 수요 증가율 데이터가 제공되지 않았습니다.",
            interpretation="수요 요인을 판단할 수 없어 해당 요인은 위험도 산정에서 제한적으로 반영됩니다.",
            data_source="국토교통부_노선별 항공통계",
            used_features=["passenger_growth_rate"],
            threshold="10% 이상 위험, 3% 이상 주의",
            is_available=False
        )

    if passenger_growth_rate >= 10:
        score = 5
        evidence = f"여객 수요가 전년 동월 대비 {passenger_growth_rate}% 증가했습니다."
        interpretation = "해당 노선에 여행 수요가 강하게 몰리고 있어, 항공권 가격이 오르기 쉬운 조건으로 볼 수 있습니다."
    elif passenger_growth_rate >= 3:
        score = 3
        evidence = f"여객 수요가 전년 동월 대비 {passenger_growth_rate}% 증가했습니다."
        interpretation = "수요가 완만하게 증가하고 있어 가격 변동 가능성을 지켜볼 필요가 있습니다."
    else:
        score = 1
        evidence = f"여객 수요 증가율은 {passenger_growth_rate}%로 크지 않습니다."
        interpretation = "수요 측면에서는 가격 상승 압력이 크지 않은 편입니다."

    return build_agent_result(
        factor_name="수요",
        status=get_status_by_score(score),
        score=score,
        evidence=evidence,
        interpretation=interpretation,
        data_source="국토교통부_노선별 항공통계",
        used_features=["passenger_growth_rate"],
        threshold="10% 이상 위험, 3% 이상 주의"
    )


def supply_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    passenger_growth_rate = data.get("passenger_growth_rate")
    flight_growth_rate = data.get("flight_growth_rate")

    if passenger_growth_rate is None or flight_growth_rate is None:
        return build_agent_result(
            factor_name="공급",
            status="정보 부족",
            score=0,
            evidence="여객 증가율 또는 운항편 증가율 데이터가 제공되지 않았습니다.",
            interpretation="수요 대비 공급 부족 여부를 판단하기 어렵습니다.",
            data_source="국토교통부_노선별 항공통계 / 공항별 항공통계",
            used_features=["passenger_growth_rate", "flight_growth_rate"],
            threshold="여객 증가율 - 운항편 증가율이 8%p 이상이면 위험",
            is_available=False
        )

    supply_demand_gap = passenger_growth_rate - flight_growth_rate

    if supply_demand_gap >= 8:
        score = 5
        evidence = (
            f"여객 증가율은 {passenger_growth_rate}%인 반면, "
            f"운항편 증가율은 {flight_growth_rate}%입니다."
        )
        interpretation = "수요는 빠르게 늘고 있지만 운항편 공급은 충분히 늘지 않아, 좌석 확보 경쟁이 커질 수 있습니다."
    elif supply_demand_gap >= 3:
        score = 3
        evidence = f"여객 증가율이 운항편 증가율보다 {round(supply_demand_gap, 1)}%p 높습니다."
        interpretation = "수요 증가에 비해 공급 여유가 넉넉하지 않을 수 있어 가격 변동을 확인할 필요가 있습니다."
    else:
        score = 1
        evidence = "운항편 공급이 여객 수요 변화와 비교해 크게 부족한 상황은 아닙니다."
        interpretation = "공급 측면에서는 가격 상승 압력이 제한적인 편입니다."

    return build_agent_result(
        factor_name="공급",
        status=get_status_by_score(score),
        score=score,
        evidence=evidence,
        interpretation=interpretation,
        data_source="국토교통부_노선별 항공통계 / 공항별 항공통계",
        used_features=["passenger_growth_rate", "flight_growth_rate"],
        threshold="수요-공급 격차 8%p 이상 위험, 3%p 이상 주의"
    )


def holiday_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    days_to_holiday = data.get("days_to_holiday")
    holiday_name = data.get("holiday_name", "공휴일")

    if days_to_holiday is None:
        return build_agent_result(
            factor_name="연휴/시기",
            status="정보 부족",
            score=0,
            evidence="공휴일 또는 연휴 인접 정보가 제공되지 않았습니다.",
            interpretation="시기적 수요 집중 여부를 판단하기 어렵습니다.",
            data_source="한국천문연구원_특일 정보",
            used_features=["days_to_holiday", "holiday_name"],
            threshold="3일 이내 위험, 7일 이내 주의",
            is_available=False
        )

    if days_to_holiday <= 3:
        score = 5
        evidence = f"출발일이 {holiday_name}까지 {days_to_holiday}일 남은 시점입니다."
        interpretation = "연휴 직전에는 여행 수요가 집중되기 쉬워 항공권 가격이 불리해질 가능성이 있습니다."
    elif days_to_holiday <= 7:
        score = 3
        evidence = f"출발일이 {holiday_name}과 가까운 시점입니다."
        interpretation = "연휴 인접 수요가 일부 반영될 수 있어 가격 변동 가능성이 있습니다."
    else:
        score = 1
        evidence = "출발일이 주요 공휴일 또는 연휴와 직접적으로 가깝지는 않습니다."
        interpretation = "연휴 요인으로 인한 가격 상승 위험은 제한적인 편입니다."

    return build_agent_result(
        factor_name="연휴/시기",
        status=get_status_by_score(score),
        score=score,
        evidence=evidence,
        interpretation=interpretation,
        data_source="한국천문연구원_특일 정보",
        used_features=["days_to_holiday", "holiday_name"],
        threshold="3일 이내 위험, 7일 이내 주의"
    )


def exchange_rate_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    exchange_rate_change = data.get("jpy_krw_change_rate")

    if exchange_rate_change is None:
        return build_agent_result(
            factor_name="환율",
            status="정보 부족",
            score=0,
            evidence="엔화 환율 변화율 데이터가 제공되지 않았습니다.",
            interpretation="환율 요인을 판단할 수 없습니다.",
            data_source="한국수출입은행 환율 정보",
            used_features=["jpy_krw_change_rate"],
            threshold="5% 이상 위험, 2% 이상 주의",
            is_available=False
        )

    if exchange_rate_change >= 5:
        score = 5
        evidence = f"엔화 환율이 최근 {exchange_rate_change}% 상승했습니다."
        interpretation = "엔화 환율 상승은 일본 여행의 원화 기준 부담을 키울 수 있어 구매 판단에 영향을 줄 수 있습니다."
    elif exchange_rate_change >= 2:
        score = 3
        evidence = f"엔화 환율이 최근 {exchange_rate_change}% 상승했습니다."
        interpretation = "환율 변동으로 인해 일본 여행 비용 부담이 일부 커질 수 있습니다."
    else:
        score = 1
        evidence = f"엔화 환율 변화율은 {exchange_rate_change}%로 크지 않습니다."
        interpretation = "환율 측면의 추가 부담은 제한적인 편입니다."

    return build_agent_result(
        factor_name="환율",
        status=get_status_by_score(score),
        score=score,
        evidence=evidence,
        interpretation=interpretation,
        data_source="한국수출입은행 환율 정보",
        used_features=["jpy_krw_change_rate"],
        threshold="5% 이상 위험, 2% 이상 주의"
    )


def operation_agent(data: Dict[str, Any]) -> Dict[str, Any]:
    delay_rate = data.get("delay_rate")
    cancel_count = data.get("cancel_count")

    if delay_rate is None or cancel_count is None:
        return build_agent_result(
            factor_name="운항 상황",
            status="정보 부족",
            score=0,
            evidence="지연율 또는 결항 건수 데이터가 제공되지 않았습니다.",
            interpretation="운항 리스크를 판단하기 어렵습니다.",
            data_source="인천국제공항공사_여객편 주간 운항 현황 / 한국공항공사_실시간 항공기 운항정보",
            used_features=["delay_rate", "cancel_count"],
            threshold="결항 1건 이상 또는 지연율 20% 이상 위험",
            is_available=False
        )

    if cancel_count > 0 or delay_rate >= 20:
        score = 5
        evidence = f"최근 운항 데이터에서 지연율 {delay_rate}%, 결항 {cancel_count}건이 확인되었습니다."
        interpretation = "운항이 불안정하면 특정 시간대나 대체편으로 수요가 몰릴 수 있습니다."
    elif delay_rate >= 10:
        score = 3
        evidence = f"최근 운항 지연율이 {delay_rate}%로 확인되었습니다."
        interpretation = "운항 상황을 지속적으로 확인할 필요가 있습니다."
    else:
        score = 1
        evidence = "현재 큰 지연 또는 결항 리스크는 확인되지 않았습니다."
        interpretation = "운항 리스크는 현재 구매 판단에 큰 영향을 주지 않는 것으로 보입니다."

    return build_agent_result(
        factor_name="운항 상황",
        status=get_status_by_score(score),
        score=score,
        evidence=evidence,
        interpretation=interpretation,
        data_source="인천국제공항공사_여객편 주간 운항 현황 / 한국공항공사_실시간 항공기 운항정보",
        used_features=["delay_rate", "cancel_count"],
        threshold="결항 1건 이상 또는 지연율 20% 이상 위험, 지연율 10% 이상 주의"
    )


def calculate_confidence(agent_results: Dict[str, Dict[str, Any]], input_data: Dict[str, Any]) -> str:
    available_agents = [
        result for result in agent_results.values()
        if result.get("is_available", True)
    ]

    high_or_medium_agents = [
        result for result in available_agents
        if result["score"] >= 3
    ]

    core_fields = [
        "passenger_growth_rate",
        "flight_growth_rate",
        "days_to_holiday",
        "jpy_krw_change_rate"
    ]

    available_core_count = sum(
        1 for field in core_fields
        if input_data.get(field) is not None
    )

    if len(available_agents) >= 5 and available_core_count >= 4 and len(high_or_medium_agents) >= 2:
        return "높음"

    if len(available_agents) >= 4 and available_core_count >= 3:
        return "중간"

    return "낮음"


def decision_agent(
    agent_results: Dict[str, Dict[str, Any]],
    input_data: Dict[str, Any]
) -> Dict[str, Any]:
    total_score = sum(result["score"] for result in agent_results.values())
    max_score = sum(result.get("max_score", 5) for result in agent_results.values())

    if total_score >= 16:
        risk_level = "높음"
        recommendation = "빠른 구매 검토"
        summary = (
            "지금 조건에서는 항공권 구매를 오래 미루기보다 빠르게 가격을 확인하는 편이 유리할 수 있습니다. "
            "수요 증가, 공급 제한, 연휴 인접 등 여러 요인이 겹쳐 가격이 불리해질 가능성이 있습니다."
        )
    elif total_score >= 8:
        risk_level = "보통"
        recommendation = "가격 변동 지속 확인"
        summary = (
            "일부 가격 상승 요인이 확인되지만, 모든 조건이 강하게 불리한 상황은 아닙니다. "
            "며칠간 가격 변동을 확인하면서 구매 시점을 판단하는 것이 적절합니다."
        )
    else:
        risk_level = "낮음"
        recommendation = "대기 가능"
        summary = (
            "현재 조건에서는 가격 상승 위험 요인이 크지 않은 편입니다. "
            "일정에 여유가 있다면 추가 가격 확인 후 구매를 결정할 수 있습니다."
        )

    confidence = calculate_confidence(agent_results, input_data)

    return {
        "risk_score": total_score,
        "max_score": max_score,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "confidence": confidence,
        "summary": summary
    }


def run_agent_pipeline(data: Dict[str, Any]) -> Dict[str, Any]:
    validate_agent_input(data)

    factor_analysis = {
        "demand": demand_agent(data),
        "supply": supply_agent(data),
        "holiday": holiday_agent(data),
        "exchange_rate": exchange_rate_agent(data),
        "operation": operation_agent(data)
    }

    risk_assessment = decision_agent(factor_analysis, data)

    risk_result = {
        "service": {
            "name": "LLM 기반 항공권 구매 타이밍 의사결정 지원 서비스",
            "analysis_version": "v0.4.0",
            "data_basis": "공공데이터 기반 위험도 산정 결과",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "user_query": {
            "original_text": data["original_text"],
            "departure_airport": data["departure_airport"],
            "arrival_airport": data["arrival_airport"],
            "route_name": data["route_name"],
            "departure_date": data["departure_date"]
        },
        "risk_assessment": risk_assessment,
        "factor_analysis": factor_analysis,
        "limitations": [
            "실제 항공권 판매 가격 데이터는 포함되어 있지 않음",
            "항공사 내부 예약률 및 잔여 좌석 수는 확인할 수 없음",
            "분석 결과는 가격 예측값이 아니라 가격 상승 위험도 판단 결과임",
            "What-if 시뮬레이션은 현재 테스트용 가정값을 기반으로 함"
        ]
    }

    return risk_result