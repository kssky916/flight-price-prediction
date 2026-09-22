from datetime import datetime

SUPPORTED_AIRPORTS = {
    "ICN": "인천",
    "GMP": "김포",
    "PUS": "김해",
    "CJU": "제주",
    "NRT": "도쿄 나리타",
    "HND": "도쿄 하네다",
    "KIX": "오사카 간사이",
    "FUK": "후쿠오카",
    "CTS": "삿포로",
    "OKA": "오키나와",
    "NGO": "나고야",
}


def normalize_airport_code(value):
    if value is None:
        return value

    value = str(value).strip()

    mapping = {
        "인천(ICN)": "ICN",
        "인천": "ICN",
        "ICN": "ICN",
        "김포(GMP)": "GMP",
        "김포": "GMP",
        "GMP": "GMP",
        "김해(PUS)": "PUS",
        "부산(PUS)": "PUS",
        "부산": "PUS",
        "PUS": "PUS",
        "제주(CJU)": "CJU",
        "제주": "CJU",
        "CJU": "CJU",
        "나리타(NRT)": "NRT",
        "도쿄 나리타(NRT)": "NRT",
        "NRT": "NRT",
        "하네다(HND)": "HND",
        "도쿄 하네다(HND)": "HND",
        "HND": "HND",
        "간사이(KIX)": "KIX",
        "오사카(KIX)": "KIX",
        "오사카 간사이(KIX)": "KIX",
        "KIX": "KIX",
        "후쿠오카(FUK)": "FUK",
        "FUK": "FUK",
        "삿포로(CTS)": "CTS",
        "CTS": "CTS",
        "오키나와(OKA)": "OKA",
        "OKA": "OKA",
        "나고야(NGO)": "NGO",
        "NGO": "NGO",
    }

    return mapping.get(value, value)


def validate_agent_input(data: dict) -> None:
    required_fields = [
        "departure_airport",
        "arrival_airport",
        "departure_date",
        "passenger_growth_rate",
        "flight_growth_rate",
        "days_to_holiday",
        "jpy_krw_change_rate",
        "delay_rate",
        "cancel_count",
    ]

    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        raise ValueError(f"필수 입력값이 누락되었습니다: {missing_fields}")

    data["departure_airport"] = normalize_airport_code(data["departure_airport"])
    data["arrival_airport"] = normalize_airport_code(data["arrival_airport"])

    if data["departure_airport"] not in SUPPORTED_AIRPORTS:
        raise ValueError(f"지원하지 않는 출발 공항 코드입니다: {data['departure_airport']}")

    if data["arrival_airport"] not in SUPPORTED_AIRPORTS:
        raise ValueError(f"지원하지 않는 도착 공항 코드입니다: {data['arrival_airport']}")

    try:
        datetime.fromisoformat(str(data["departure_date"]))
    except ValueError:
        raise ValueError(f"출발일 형식이 올바르지 않습니다: {data['departure_date']}")

    numeric_fields = [
        "passenger_growth_rate",
        "flight_growth_rate",
        "days_to_holiday",
        "jpy_krw_change_rate",
        "delay_rate",
        "cancel_count",
    ]

    for field in numeric_fields:
        try:
            data[field] = float(data[field])
        except Exception:
            raise ValueError(f"{field} 값은 숫자여야 합니다: {data[field]}")
