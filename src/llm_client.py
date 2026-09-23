import os
import json
import re
import csv
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List, Optional

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
HOLIDAY_PATH = ROOT_DIR / "data" / "processed" / "processed_holidays_clean.csv"

load_dotenv(dotenv_path=ENV_PATH)


HOLIDAY_KEYWORDS = {
    "크리스마스": ["크리스마스", "성탄절", "christmas"],
    "성탄절": ["크리스마스", "성탄절", "christmas"],
    "설날": ["설날", "설", "구정"],
    "추석": ["추석", "한가위"],
    "삼일절": ["삼일절", "3.1절", "3·1절"],
    "어린이날": ["어린이날"],
    "부처님오신날": ["부처님오신날", "석가탄신일"],
    "현충일": ["현충일"],
    "광복절": ["광복절"],
    "개천절": ["개천절"],
    "한글날": ["한글날"],
    "신정": ["신정", "새해", "1월1일", "1월 1일"],
}


FALLBACK_HOLIDAYS = {
    2027: {
        "추석": ["2027-09-14", "2027-09-15", "2027-09-16"],
        "설날": ["2027-02-06", "2027-02-07", "2027-02-08", "2027-02-09"],
        "크리스마스": ["2027-12-25"],
        "성탄절": ["2027-12-25"],
        "신정": ["2027-01-01"],
    }
}


CITY_KEYWORDS = [
    "도쿄", "오사카", "후쿠오카", "삿포로", "오키나와", "나고야",
    "고베", "구마모토", "히로시마", "마쓰야마", "가고시마", "오이타",
    "미야자키", "다카마쓰", "센다이", "아오모리", "시즈오카", "니가타",
    "오카야마", "요나고", "기타큐슈", "이시가키", "나가사키",
]


DEPARTURE_KEYWORDS = {
    "인천": "ICN",
    "김포": "GMP",
    "부산": "PUS",
    "김해": "PUS",
    "제주": "CJU",
}


def is_llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _call_openai(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": prompt,
        },
        timeout=60,
    )

    if response.status_code >= 400:
        raise ValueError(f"OpenAI API 오류 {response.status_code}: {response.text}")

    return _extract_text_from_response(response.json())


def _extract_text_from_response(data: Dict[str, Any]) -> str:
    if data.get("output_text"):
        return data["output_text"]

    texts = []

    for item in data.get("output", []):
        for content_item in item.get("content", []):
            if content_item.get("type") in ["output_text", "text"]:
                text = content_item.get("text", "")

                if text:
                    texts.append(text)

    if texts:
        return "\n".join(texts)

    raise ValueError(f"AI 응답에서 텍스트를 찾지 못했습니다: {data}")


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)

    if not match:
        raise ValueError(f"AI 응답에서 JSON을 찾지 못했습니다: {text}")

    return json.loads(match.group(0))


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(int(year), int(month), int(day))
    except Exception:
        return None


def _resolve_future_year(month: int, day: int) -> int:
    today = datetime.today().date()
    candidate = _safe_date(today.year, month, day)

    if candidate and candidate >= today:
        return today.year

    return today.year + 1


def _detect_relative_year(raw_text: str) -> Optional[int]:
    today = datetime.today().date()

    if "내년" in raw_text or "다음해" in raw_text or "다음 년" in raw_text:
        return today.year + 1

    if "올해" in raw_text or "이번해" in raw_text:
        return today.year

    match = re.search(r"(20\d{2})\s*년", raw_text)

    if match:
        return int(match.group(1))

    return None


def _parse_iso_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_korean_date_range(raw_text: str) -> Dict[str, Optional[str]]:
    compact_text = re.sub(r"\s+", "", raw_text)

    patterns = [
        r"(?:(\d{4})년)?(\d{1,2})월(\d{1,2})일?(?:부터|에서|~|-|–|—)(?:(\d{4})년)?(?:(\d{1,2})월)?(\d{1,2})일?",
        r"(?:(\d{4})[./-])?(\d{1,2})[./-](\d{1,2})(?:부터|에서|~|-|–|—)(?:(\d{4})[./-])?(?:(\d{1,2})[./-])?(\d{1,2})",
    ]

    relative_year = _detect_relative_year(raw_text)

    for pattern in patterns:
        match = re.search(pattern, compact_text)

        if not match:
            continue

        start_year_text, start_month, start_day, end_year_text, end_month, end_day = match.groups()

        start_month = int(start_month)
        start_day = int(start_day)
        end_month = int(end_month) if end_month else start_month
        end_day = int(end_day)

        if start_year_text:
            start_year = int(start_year_text)
        elif relative_year:
            start_year = relative_year
        else:
            start_year = _resolve_future_year(start_month, start_day)

        if end_year_text:
            end_year = int(end_year_text)
        else:
            end_year = start_year

        start_date = _safe_date(start_year, start_month, start_day)
        end_date = _safe_date(end_year, end_month, end_day)

        if start_date and end_date and end_date < start_date:
            end_date = _safe_date(end_year + 1, end_month, end_day)

        if start_date and end_date:
            return {
                "travel_window_start": str(start_date),
                "travel_window_end": str(end_date),
            }

    return {
        "travel_window_start": None,
        "travel_window_end": None,
    }


def _parse_stay_duration(raw_text: str) -> Dict[str, Optional[int]]:
    match = re.search(r"(\d+)\s*박\s*(\d+)\s*일", raw_text)

    if match:
        return {
            "nights": int(match.group(1)),
            "days": int(match.group(2)),
        }

    match = re.search(r"(\d+)\s*박", raw_text)

    if match:
        nights = int(match.group(1))

        return {
            "nights": nights,
            "days": nights + 1,
        }

    return {
        "nights": None,
        "days": None,
    }


def _detect_destination_city(raw_text: str) -> Optional[str]:
    for city in CITY_KEYWORDS:
        if city in raw_text:
            return city

    return None


def _detect_departure_airport(raw_text: str) -> Optional[str]:
    for keyword, airport_code in DEPARTURE_KEYWORDS.items():
        if keyword in raw_text and ("출발" in raw_text or "에서" in raw_text):
            return airport_code

    return None


def _detect_holiday_names_from_text(raw_text: str) -> List[str]:
    raw_text_lower = raw_text.lower()
    detected = []

    for canonical_name, keywords in HOLIDAY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in raw_text_lower:
                detected.append(canonical_name)
                break

    return sorted(set(detected))


def _get_target_year(parsed: Dict[str, Any]) -> int:
    raw_text = str(parsed.get("raw_user_text") or "")
    relative_year = _detect_relative_year(raw_text)

    if relative_year:
        return relative_year

    for key in ["travel_window_start", "preferred_departure_date"]:
        parsed_date = _parse_iso_date(parsed.get(key))

        if parsed_date:
            return parsed_date.year

    return datetime.today().year


def _find_holiday_dates_from_csv(
    holiday_names: List[str],
    target_year: int,
    travel_window_start=None,
    travel_window_end=None,
) -> List[str]:
    if not HOLIDAY_PATH.exists() or not holiday_names:
        return []

    start_date = _parse_iso_date(travel_window_start)
    end_date = _parse_iso_date(travel_window_end)

    matched_dates = []

    with open(HOLIDAY_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            date_value = (
                row.get("holiday_date")
                or row.get("date")
                or row.get("locdate")
                or row.get("date_value")
            )

            holiday_date = _parse_iso_date(str(date_value)[:10]) if date_value else None

            if not holiday_date or holiday_date.year != target_year:
                continue

            if start_date and holiday_date < start_date:
                continue

            if end_date and holiday_date > end_date:
                continue

            row_text = " ".join([str(value) for value in row.values() if value])

            for holiday_name in holiday_names:
                keywords = HOLIDAY_KEYWORDS.get(holiday_name, [holiday_name])

                if any(keyword in row_text for keyword in keywords):
                    matched_dates.append(str(holiday_date))
                    break

    return sorted(set(matched_dates))


def _find_holiday_dates_from_fallback(
    holiday_names: List[str],
    target_year: int,
    travel_window_start=None,
    travel_window_end=None,
) -> List[str]:
    year_map = FALLBACK_HOLIDAYS.get(target_year, {})
    start_date = _parse_iso_date(travel_window_start)
    end_date = _parse_iso_date(travel_window_end)

    matched_dates = []

    for holiday_name in holiday_names:
        for date_text in year_map.get(holiday_name, []):
            holiday_date = _parse_iso_date(date_text)

            if not holiday_date:
                continue

            if start_date and holiday_date < start_date:
                continue

            if end_date and holiday_date > end_date:
                continue

            matched_dates.append(str(holiday_date))

    return sorted(set(matched_dates))


def _normalize_required_dates(parsed: Dict[str, Any]) -> Dict[str, Any]:
    raw_text = str(parsed.get("raw_user_text") or "")
    target_year = _get_target_year(parsed)

    must_include_dates = parsed.get("must_include_dates")
    if not isinstance(must_include_dates, list):
        must_include_dates = []

    must_include_holiday_names = parsed.get("must_include_holiday_names")
    if not isinstance(must_include_holiday_names, list):
        must_include_holiday_names = []

    for holiday_name in _detect_holiday_names_from_text(raw_text):
        if holiday_name not in must_include_holiday_names:
            must_include_holiday_names.append(holiday_name)

    if "크리스마스" in must_include_holiday_names or "성탄절" in must_include_holiday_names:
        christmas_date = f"{target_year}-12-25"

        if christmas_date not in must_include_dates:
            must_include_dates.append(christmas_date)

    if "신정" in must_include_holiday_names:
        new_year_date = f"{target_year}-01-01"

        if new_year_date not in must_include_dates:
            must_include_dates.append(new_year_date)

    csv_dates = _find_holiday_dates_from_csv(
        holiday_names=must_include_holiday_names,
        target_year=target_year,
        travel_window_start=parsed.get("travel_window_start"),
        travel_window_end=parsed.get("travel_window_end"),
    )

    fallback_dates = _find_holiday_dates_from_fallback(
        holiday_names=must_include_holiday_names,
        target_year=target_year,
        travel_window_start=parsed.get("travel_window_start"),
        travel_window_end=parsed.get("travel_window_end"),
    )

    for date_text in csv_dates + fallback_dates:
        if date_text not in must_include_dates:
            must_include_dates.append(date_text)

    parsed["must_include_dates"] = sorted(set(must_include_dates))
    parsed["must_include_holiday_names"] = sorted(set(must_include_holiday_names))

    return parsed


def _apply_deterministic_fallback(parsed: Dict[str, Any], user_text: str) -> Dict[str, Any]:
    raw_text = user_text.strip()

    parsed["raw_user_text"] = raw_text

    date_range = _parse_korean_date_range(raw_text)
    stay_duration = _parse_stay_duration(raw_text)

    if date_range["travel_window_start"] and date_range["travel_window_end"]:
        parsed["travel_window_start"] = date_range["travel_window_start"]
        parsed["travel_window_end"] = date_range["travel_window_end"]

        if stay_duration["nights"] is not None:
            parsed["preferred_departure_date"] = None
            parsed["preferred_return_date"] = None

    if stay_duration["nights"] is not None:
        parsed["nights"] = stay_duration["nights"]
        parsed["days"] = stay_duration["days"]

    detected_departure = _detect_departure_airport(raw_text)

    if detected_departure:
        parsed["departure_airport"] = detected_departure

    if not parsed.get("departure_airport"):
        parsed["departure_airport"] = "ICN"

    if "일본" in raw_text:
        parsed["destination_country"] = "일본"

    detected_city = _detect_destination_city(raw_text)

    if detected_city:
        parsed["destination_city"] = detected_city

    return parsed


def parse_travel_request(user_text: str) -> Dict[str, Any]:
    today = datetime.today().strftime("%Y-%m-%d")

    prompt = f"""
너는 항공권 구매 타이밍 판단 서비스의 AI 여행 조건 추출기다.

사용자의 자연어 입력에서 항공권 추천에 필요한 조건만 JSON으로 추출해라.

기준일: {today}

규칙:
- 반드시 JSON만 출력해라.
- 설명 문장, markdown, 코드블록을 출력하지 마라.
- 날짜에 연도가 없으면 기준일과 가장 가까운 미래 날짜로 해석해라.
- "내년 추석", "내년 설날"처럼 상대 연도와 공휴일만 있으면 must_include_holiday_names에 공휴일명을 넣어라.
- "12월20일~12월30일 사이", "10월1일~10월10일 휴가 기간"처럼 범위 표현이면 travel_window_start, travel_window_end에 넣어라.
- 목적지가 "일본"처럼 국가 단위면 destination_country는 "일본"으로 둔다.
- 특정 도시가 있으면 destination_city에 넣는다.
- 출발지가 없으면 departure_airport는 "ICN"으로 둔다.
- 체류 기간이 "3박4일"이면 nights=3, days=4로 추출한다.
- 체류 기간이 없으면 nights와 days는 null로 둔다.
- 여행 가능 기간이 있으면 travel_window_start, travel_window_end에 YYYY-MM-DD로 넣는다.
- 특정 출발일/도착일이 명확하면 preferred_departure_date, preferred_return_date에 넣는다.
- 사용자가 특정 날짜나 공휴일이 여행 기간 안에 포함되길 원하면 must_include_dates 또는 must_include_holiday_names에 반영한다.
- "크리스마스", "성탄절"은 must_include_holiday_names에 넣는다.
- "추석", "한가위"는 must_include_holiday_names에 넣는다.
- "설날", "설", "구정"은 must_include_holiday_names에 넣는다.
- "어린이날", "부처님오신날", "석가탄신일", "광복절", "한글날", "개천절", "현충일", "삼일절", "신정"도 인식한다.
- 불확실하거나 누락된 값은 null로 둔다.
- must_include_dates가 없으면 빈 배열 []로 둔다.
- must_include_holiday_names가 없으면 빈 배열 []로 둔다.
- 사용자가 원하는 추천 개수가 없으면 recommendation_count는 5로 둔다.

출력 JSON 형식:
{{
  "departure_airport": "ICN",
  "destination_country": "일본",
  "destination_city": null,
  "travel_window_start": "YYYY-MM-DD 또는 null",
  "travel_window_end": "YYYY-MM-DD 또는 null",
  "preferred_departure_date": "YYYY-MM-DD 또는 null",
  "preferred_return_date": "YYYY-MM-DD 또는 null",
  "nights": 3,
  "days": 4,
  "must_include_dates": ["YYYY-MM-DD"],
  "must_include_holiday_names": ["추석"],
  "recommendation_count": 5,
  "raw_user_text": "원문"
}}

사용자 입력:
{user_text}
""".strip()

    response_text = _call_openai(prompt)
    parsed = _extract_json(response_text)

    parsed.setdefault("departure_airport", "ICN")
    parsed.setdefault("destination_country", None)
    parsed.setdefault("destination_city", None)
    parsed.setdefault("travel_window_start", None)
    parsed.setdefault("travel_window_end", None)
    parsed.setdefault("preferred_departure_date", None)
    parsed.setdefault("preferred_return_date", None)
    parsed.setdefault("nights", None)
    parsed.setdefault("days", None)
    parsed.setdefault("must_include_dates", [])
    parsed.setdefault("must_include_holiday_names", [])
    parsed.setdefault("recommendation_count", 5)
    parsed.setdefault("raw_user_text", user_text)

    if not isinstance(parsed.get("must_include_dates"), list):
        parsed["must_include_dates"] = []

    if not isinstance(parsed.get("must_include_holiday_names"), list):
        parsed["must_include_holiday_names"] = []

    parsed = _apply_deterministic_fallback(parsed, user_text)
    parsed = _normalize_required_dates(parsed)

    return parsed


def build_llm_prompt(risk_result: Dict[str, Any]) -> str:
    factor_details = risk_result.get("factor_details", [])
    evidence = risk_result.get("evidence", [])

    factor_lines = []

    for item in factor_details:
        factor_lines.append(
            f"- {item.get('factor')}: {item.get('score')}/{item.get('max_score')}점, {item.get('reason')}"
        )

    evidence_lines = []

    for item in evidence[:12]:
        evidence_lines.append(f"- {item}")

    return f"""
너는 항공권 구매 타이밍 판단 서비스의 AI 2차 검토 에이전트다.

이 서비스의 1차 판단은 공공데이터 기반 Rule-based scoring으로 산정된다.
너의 역할은 1차 판단 결과와 사용된 데이터를 다시 검토하여,
최종 사용자용 구매 타이밍 판단과 근거를 정리하는 것이다.

반드시 지켜야 할 규칙:
- 실제 항공권 가격을 예측했다고 말하지 마라.
- 존재하지 않는 실시간 항공권 가격, 실시간 검색 결과, 예약률을 지어내지 마라.
- 주어진 점수와 데이터 근거 안에서만 판단해라.
- AI가 독자적으로 가격을 예측한다고 말하지 마라.
- 1차 Rule-based 결과를 무조건 그대로 복사하지 말고, 데이터 간 모순이나 보완점이 있는지 검토해라.
- 단, 근거 없이 1차 판단을 뒤집지 마라.
- 최종 판단은 아래 셋 중 하나만 사용해라:
  1) 빠른 구매 검토
  2) 가격 모니터링 후 구매
  3) 대기 가능
- 한국어로 작성해라.
- 사용자가 바로 이해할 수 있게 짧고 명확하게 작성해라.

[1차 Rule-based 판단 결과]
노선: {risk_result.get("departure_airport")} → {risk_result.get("arrival_airport")}
출발일: {risk_result.get("departure_date")}
1차 위험도: {risk_result.get("risk_level")}
1차 위험도 점수: {risk_result.get("risk_score")} / {risk_result.get("max_score")}
1차 구매 판단: {risk_result.get("purchase_timing_recommendation")}
1차 판단 요약: {risk_result.get("decision_reason")}

[요인별 점수]
{chr(10).join(factor_lines)}

[사용 데이터 근거]
{chr(10).join(evidence_lines)}

너는 위 정보를 바탕으로 아래 형식으로만 답변해라.

### AI 2차 검토 결과

#### 1. 최종 구매 판단
- 빠른 구매 검토 / 가격 모니터링 후 구매 / 대기 가능 중 하나로 명확히 작성
- 한 문장으로 이유 요약

#### 2. 1차 판단 검토
- Rule-based 판단이 데이터와 잘 맞는지 검토
- 유지할지, 보수적으로 조정해서 해석할지 설명

#### 3. 핵심 근거
- 가장 중요한 근거 3개만 bullet로 작성
- 각 근거는 데이터 기반으로 설명

#### 4. 주의할 점
- 데이터상 한계나 해석 시 주의할 점을 1~2개 작성
- 없는 정보를 지어내지 말 것

#### 5. 사용자 행동 가이드
- 사용자가 지금 어떤 행동을 하면 되는지 한 문장으로 마무리
""".strip()


def generate_llm_explanation(risk_result: Dict[str, Any]) -> str:
    prompt = build_llm_prompt(risk_result)
    return _call_openai(prompt)
