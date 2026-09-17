from datetime import datetime
from typing import Dict, Any


SUPPORTED_AIRPORT_CODES = {
    "ICN", "GMP", "PUS", "CJU",
    "NRT", "HND", "KIX", "FUK", "CTS", "OKA"
}


REQUIRED_FIELDS = [
    "original_text",
    "departure_airport",
    "arrival_airport",
    "route_name",
    "departure_date",
    "passenger_growth_rate",
    "flight_growth_rate",
    "days_to_holiday",
    "holiday_name",
    "jpy_krw_change_rate",
    "delay_rate",
    "cancel_count"
]


NUMERIC_FIELDS = [
    "passenger_growth_rate",
    "flight_growth_rate",
    "days_to_holiday",
    "jpy_krw_change_rate",
    "delay_rate",
    "cancel_count"
]


def validate_agent_input(data: Dict[str, Any]) -> None:
    missing_fields = [
        field for field in REQUIRED_FIELDS
        if field not in data or data[field] is None
    ]

    if missing_fields:
        raise ValueError(f"필수 입력값이 누락되었습니다: {missing_fields}")

    if data["departure_airport"] not in SUPPORTED_AIRPORT_CODES:
        raise ValueError(f"지원하지 않는 출발 공항 코드입니다: {data['departure_airport']}")

    if data["arrival_airport"] not in SUPPORTED_AIRPORT_CODES:
        raise ValueError(f"지원하지 않는 도착 공항 코드입니다: {data['arrival_airport']}")

    for field in NUMERIC_FIELDS:
        if not isinstance(data[field], (int, float)):
            raise TypeError(f"{field}는 숫자여야 합니다. 현재 값: {data[field]}")

    try:
        datetime.fromisoformat(str(data["departure_date"]))
    except ValueError as exc:
        raise ValueError(
            f"departure_date는 YYYY-MM-DD 형식이어야 합니다. 현재 값: {data['departure_date']}"
        ) from exc

    if data["days_to_holiday"] < 0:
        raise ValueError("days_to_holiday는 0 이상이어야 합니다.")

    if data["delay_rate"] < 0:
        raise ValueError("delay_rate는 0 이상이어야 합니다.")

    if data["cancel_count"] < 0:
        raise ValueError("cancel_count는 0 이상이어야 합니다.")