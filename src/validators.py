from datetime import datetime
import re

SUPPORTED_AIRPORTS = {
    "ICN": "인천",
    "GMP": "김포",
    "PUS": "김해",
    "CJU": "제주",

    # 일본 주요 공항
    "NRT": "도쿄 나리타",
    "HND": "도쿄 하네다",
    "KIX": "오사카 간사이",
    "FUK": "후쿠오카",
    "CTS": "삿포로",
    "OKA": "오키나와",
    "NGO": "나고야",
    "UKB": "고베",
    "KMJ": "구마모토",
    "HIJ": "히로시마",
    "MYJ": "마쓰야마",
    "KOJ": "가고시마",
    "OIT": "오이타",
    "KMI": "미야자키",
    "TAK": "다카마쓰",
    "SDJ": "센다이",
    "AOJ": "아오모리",
    "FSZ": "시즈오카",
    "KIJ": "니가타",
    "OKJ": "오카야마",
    "YGJ": "요나고",
    "KKJ": "기타큐슈",
    "ISG": "이시가키",
    "NGS": "나가사키",
}


AIRPORT_NAME_TO_CODE = {
    "한국": "ICN",
    "인천": "ICN",
    "인천국제공항": "ICN",
    "김포": "GMP",
    "김해": "PUS",
    "부산": "PUS",
    "제주": "CJU",

    "도쿄": "NRT",
    "나리타": "NRT",
    "도쿄 나리타": "NRT",
    "하네다": "HND",
    "도쿄 하네다": "HND",
    "오사카": "KIX",
    "간사이": "KIX",
    "오사카 간사이": "KIX",
    "후쿠오카": "FUK",
    "삿포로": "CTS",
    "오키나와": "OKA",
    "나고야": "NGO",
    "고베": "UKB",
    "구마모토": "KMJ",
    "구마모도": "KMJ",
    "히로시마": "HIJ",
    "마쓰야마": "MYJ",
    "마츠야마": "MYJ",
    "가고시마": "KOJ",
    "오이타": "OIT",
    "미야자키": "KMI",
    "다카마쓰": "TAK",
    "다카마츠": "TAK",
    "센다이": "SDJ",
    "아오모리": "AOJ",
    "시즈오카": "FSZ",
    "니가타": "KIJ",
    "오카야마": "OKJ",
    "요나고": "YGJ",
    "기타큐슈": "KKJ",
    "이시가키": "ISG",
    "나가사키": "NGS",
}


def normalize_airport_code(value):
    if value is None:
        return value

    value = str(value).strip()

    # 이미 IATA 코드면 그대로 사용
    if value in SUPPORTED_AIRPORTS:
        return value

    # 예: 고베(UKB), 인천(ICN), 오사카 간사이(KIX)
    match = re.search(r"\(([A-Z]{3})\)", value)
    if match:
        code = match.group(1)
        if code in SUPPORTED_AIRPORTS:
            return code

    # 괄호 제거 후 이름 매칭
    name_only = re.sub(r"\([A-Z]{3}\)", "", value).strip()

    if name_only in AIRPORT_NAME_TO_CODE:
        return AIRPORT_NAME_TO_CODE[name_only]

    if value in AIRPORT_NAME_TO_CODE:
        return AIRPORT_NAME_TO_CODE[value]

    return value


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