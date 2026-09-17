import json
import os
import re
from datetime import datetime
from typing import Dict, Any

from dotenv import load_dotenv


load_dotenv()


SUPPORTED_AIRPORTS = {
    "인천": "ICN",
    "인천공항": "ICN",
    "김포": "GMP",
    "김포공항": "GMP",
    "김해": "PUS",
    "부산": "PUS",
    "제주": "CJU",
    "도쿄": "NRT",
    "나리타": "NRT",
    "하네다": "HND",
    "오사카": "KIX",
    "간사이": "KIX",
    "후쿠오카": "FUK",
    "삿포로": "CTS",
    "오키나와": "OKA",
}


def is_openai_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def normalize_airport_code(value: str | None) -> str | None:
    if not value:
        return None

    value = value.strip().upper()

    valid_codes = {"ICN", "GMP", "PUS", "CJU", "NRT", "HND", "KIX", "FUK", "CTS", "OKA"}

    if value in valid_codes:
        return value

    return SUPPORTED_AIRPORTS.get(value)


def parse_date_rule_based(text: str) -> str | None:
    current_year = datetime.now().year

    exact_date_match = re.search(r"(20\d{2})[-./년\s]*(\d{1,2})[-./월\s]*(\d{1,2})", text)
    if exact_date_match:
        year = int(exact_date_match.group(1))
        month = int(exact_date_match.group(2))
        day = int(exact_date_match.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    month_day_match = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if month_day_match:
        month = int(month_day_match.group(1))
        day = int(month_day_match.group(2))
        return f"{current_year:04d}-{month:02d}-{day:02d}"

    late_month_match = re.search(r"(\d{1,2})월\s*말", text)
    if late_month_match:
        month = int(late_month_match.group(1))
        return f"{current_year:04d}-{month:02d}-25"

    early_month_match = re.search(r"(\d{1,2})월\s*초", text)
    if early_month_match:
        month = int(early_month_match.group(1))
        return f"{current_year:04d}-{month:02d}-05"

    mid_month_match = re.search(r"(\d{1,2})월\s*중순", text)
    if mid_month_match:
        month = int(mid_month_match.group(1))
        return f"{current_year:04d}-{month:02d}-15"

    return None


def parse_query_rule_based(user_query: str) -> Dict[str, Any]:
    departure_airport = None
    arrival_airport = None

    for keyword, code in SUPPORTED_AIRPORTS.items():
        if keyword in user_query:
            if code in {"ICN", "GMP", "PUS", "CJU"} and departure_airport is None:
                departure_airport = code
            elif code in {"NRT", "HND", "KIX", "FUK", "CTS", "OKA"} and arrival_airport is None:
                arrival_airport = code

    if departure_airport is None:
        departure_airport = "ICN"

    departure_date = parse_date_rule_based(user_query)

    missing_fields = []
    if not departure_airport:
        missing_fields.append("departure_airport")
    if not arrival_airport:
        missing_fields.append("arrival_airport")
    if not departure_date:
        missing_fields.append("departure_date")

    return {
        "parse_success": len(missing_fields) == 0,
        "departure_airport": departure_airport,
        "arrival_airport": arrival_airport,
        "departure_date": departure_date,
        "intent": "buy_timing_check",
        "confidence": "낮음",
        "missing_fields": missing_fields,
        "explanation": "규칙 기반으로 사용자 질문에서 여행 조건을 추출했습니다.",
        "llm_used": False,
        "error_message": None,
    }


def parse_query_with_llm(user_query: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        fallback = parse_query_rule_based(user_query)
        fallback["error_message"] = "OPENAI_API_KEY가 없어 규칙 기반 파싱을 사용했습니다."
        return fallback

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "parse_success": {"type": "boolean"},
                "departure_airport": {
                    "type": ["string", "null"],
                    "description": "출발 공항 코드. ICN, GMP, PUS, CJU 중 하나."
                },
                "arrival_airport": {
                    "type": ["string", "null"],
                    "description": "도착 공항 코드. NRT, HND, KIX, FUK, CTS, OKA 중 하나."
                },
                "departure_date": {
                    "type": ["string", "null"],
                    "description": "YYYY-MM-DD 형식 출발일. 모호하면 null."
                },
                "intent": {
                    "type": "string",
                    "description": "사용자 의도. 기본값은 buy_timing_check."
                },
                "confidence": {
                    "type": "string",
                    "enum": ["높음", "중간", "낮음"]
                },
                "missing_fields": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "explanation": {"type": "string"}
            },
            "required": [
                "parse_success",
                "departure_airport",
                "arrival_airport",
                "departure_date",
                "intent",
                "confidence",
                "missing_fields",
                "explanation"
            ]
        }

        system_prompt = """
너는 항공권 구매 타이밍 서비스의 사용자 질문 해석기다.
사용자 자연어 질문에서 출발 공항, 도착 공항, 출발일, 의도를 추출한다.

지원 공항 코드는 다음만 허용한다.
출발: ICN(인천), GMP(김포), PUS(김해/부산), CJU(제주)
도착: NRT(도쿄 나리타), HND(도쿄 하네다), KIX(오사카), FUK(후쿠오카), CTS(삿포로), OKA(오키나와)

규칙:
- 사용자가 도쿄라고만 말하면 기본값은 NRT로 둔다.
- 사용자가 출발지를 말하지 않으면 기본값은 ICN으로 둔다.
- 날짜가 너무 모호하면 departure_date는 null로 둔다.
- 가격 예측이나 예약률을 추정하지 않는다.
- 반드시 JSON Schema에 맞게 답한다.
""".strip()

        current_date = datetime.now().strftime("%Y-%m-%d")

        user_prompt = f"""
현재 날짜: {current_date}

사용자 질문:
{user_query}

위 질문에서 항공권 구매 타이밍 분석에 필요한 조건을 추출하라.
""".strip()

        response = client.responses.create(
            model="gpt-5-mini",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "flight_query_parser",
                    "schema": schema,
                    "strict": True,
                }
            },
        )

        parsed = json.loads(response.output_text)

        parsed["departure_airport"] = normalize_airport_code(parsed.get("departure_airport"))
        parsed["arrival_airport"] = normalize_airport_code(parsed.get("arrival_airport"))
        parsed["llm_used"] = True
        parsed["error_message"] = None

        missing_fields = []
        if not parsed.get("departure_airport"):
            missing_fields.append("departure_airport")
        if not parsed.get("arrival_airport"):
            missing_fields.append("arrival_airport")
        if not parsed.get("departure_date"):
            missing_fields.append("departure_date")

        parsed["missing_fields"] = missing_fields
        parsed["parse_success"] = len(missing_fields) == 0

        return parsed

    except Exception as error:
        fallback = parse_query_rule_based(user_query)
        fallback["error_message"] = str(error)
        return fallback