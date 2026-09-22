import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

import pandas as pd

from src.data_loader import find_route_feature
from src.agents import run_agent_pipeline


ROOT_DIR = Path(__file__).resolve().parents[1]
HOLIDAY_PATH = ROOT_DIR / "data" / "processed" / "processed_holidays_clean.csv"


CITY_TO_AIRPORT = {
    "도쿄": ["NRT", "HND"],
    "오사카": ["KIX"],
    "후쿠오카": ["FUK"],
    "삿포로": ["CTS"],
    "오키나와": ["OKA"],
    "나고야": ["NGO"],
    "고베": ["UKB"],
    "구마모토": ["KMJ"],
    "히로시마": ["HIJ"],
    "마쓰야마": ["MYJ"],
    "가고시마": ["KOJ"],
    "오이타": ["OIT"],
    "미야자키": ["KMI"],
    "다카마쓰": ["TAK"],
    "센다이": ["SDJ"],
    "아오모리": ["AOJ"],
    "시즈오카": ["FSZ"],
    "니가타": ["KIJ"],
    "오카야마": ["OKJ"],
    "요나고": ["YGJ"],
    "기타큐슈": ["KKJ"],
    "이시가키": ["ISG"],
    "나가사키": ["NGS"],
}


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
        "설날": ["2027-02-06", "2027-02-07", "2027-02-08", "2027-02-09"],
        "추석": ["2027-09-14", "2027-09-15", "2027-09-16"],
        "크리스마스": ["2027-12-25"],
        "성탄절": ["2027-12-25"],
        "신정": ["2027-01-01"],
        "삼일절": ["2027-03-01"],
        "어린이날": ["2027-05-05"],
        "부처님오신날": ["2027-05-13"],
        "현충일": ["2027-06-06"],
        "광복절": ["2027-08-15"],
        "개천절": ["2027-10-03"],
        "한글날": ["2027-10-09"],
    }
}


DEPARTURE_KEYWORDS = {
    "인천": "ICN",
    "김포": "GMP",
    "부산": "PUS",
    "김해": "PUS",
    "제주": "CJU",
}


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


def _parse_date(value):
    if not value:
        return None

    try:
        return pd.to_datetime(str(value)[:10]).date()
    except Exception:
        return None


def _coerce_list(value):
    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [value]


def _parse_korean_date_range(raw_text: str) -> Dict[str, Optional[str]]:
    compact_text = re.sub(r"\s+", "", raw_text)
    relative_year = _detect_relative_year(raw_text)

    patterns = [
        r"(?:(\d{4})년)?(\d{1,2})월(\d{1,2})일?(?:부터|에서|~|-|–|—)(?:(\d{4})년)?(?:(\d{1,2})월)?(\d{1,2})일?",
        r"(?:(\d{4})[./-])?(\d{1,2})[./-](\d{1,2})(?:부터|에서|~|-|–|—)(?:(\d{4})[./-])?(?:(\d{1,2})[./-])?(\d{1,2})",
    ]

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


def _detect_departure_airport(raw_text: str) -> Optional[str]:
    for keyword, code in DEPARTURE_KEYWORDS.items():
        if keyword in raw_text and ("출발" in raw_text or "에서" in raw_text):
            return code

    return None


def _detect_destination_city(raw_text: str) -> Optional[str]:
    for city in CITY_TO_AIRPORT.keys():
        if city in raw_text:
            return city

    return None


def _detect_holiday_names(raw_text: str) -> List[str]:
    raw_text_lower = raw_text.lower()
    detected = []

    for holiday_name, keywords in HOLIDAY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in raw_text_lower:
                detected.append(holiday_name)
                break

    return sorted(set(detected))


def _get_target_year(parsed_request: Dict[str, Any]) -> int:
    raw_text = str(parsed_request.get("raw_user_text") or "")
    relative_year = _detect_relative_year(raw_text)

    if relative_year:
        return relative_year

    for key in ["travel_window_start", "preferred_departure_date"]:
        parsed_date = _parse_date(parsed_request.get(key))

        if parsed_date:
            return parsed_date.year

    return datetime.today().year


def _find_holiday_dates_from_csv(
    holiday_names: List[str],
    target_year: int,
    travel_window_start=None,
    travel_window_end=None,
) -> List[str]:
    if not HOLIDAY_PATH.exists():
        return []

    if not holiday_names:
        return []

    start_date = _parse_date(travel_window_start)
    end_date = _parse_date(travel_window_end)

    try:
        holiday_df = pd.read_csv(HOLIDAY_PATH, encoding="utf-8-sig")
    except Exception:
        return []

    matched_dates = []

    for _, row in holiday_df.iterrows():
        date_value = (
            row.get("holiday_date")
            or row.get("date")
            or row.get("locdate")
            or row.get("date_value")
        )

        holiday_date = _parse_date(date_value)

        if not holiday_date:
            continue

        if holiday_date.year != target_year:
            continue

        if start_date and holiday_date < start_date:
            continue

        if end_date and holiday_date > end_date:
            continue

        row_text = " ".join([str(value) for value in row.values if pd.notna(value)])

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
    start_date = _parse_date(travel_window_start)
    end_date = _parse_date(travel_window_end)

    matched_dates = []

    for holiday_name in holiday_names:
        for date_text in year_map.get(holiday_name, []):
            holiday_date = _parse_date(date_text)

            if not holiday_date:
                continue

            if start_date and holiday_date < start_date:
                continue

            if end_date and holiday_date > end_date:
                continue

            matched_dates.append(str(holiday_date))

    return sorted(set(matched_dates))


def complete_parsed_request(parsed_request: Dict[str, Any]) -> Dict[str, Any]:
    parsed = dict(parsed_request)
    raw_text = str(parsed.get("raw_user_text") or "").strip()

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

    if raw_text:
        date_range = _parse_korean_date_range(raw_text)
        stay_duration = _parse_stay_duration(raw_text)

        if date_range["travel_window_start"] and date_range["travel_window_end"]:
            parsed["travel_window_start"] = date_range["travel_window_start"]
            parsed["travel_window_end"] = date_range["travel_window_end"]
            parsed["preferred_departure_date"] = None
            parsed["preferred_return_date"] = None

        if stay_duration["nights"] is not None:
            parsed["nights"] = stay_duration["nights"]
            parsed["days"] = stay_duration["days"]

        detected_departure = _detect_departure_airport(raw_text)

        if detected_departure:
            parsed["departure_airport"] = detected_departure

        if "일본" in raw_text:
            parsed["destination_country"] = "일본"

        detected_city = _detect_destination_city(raw_text)

        if detected_city:
            parsed["destination_city"] = detected_city

        holiday_names = _coerce_list(parsed.get("must_include_holiday_names"))

        for holiday_name in _detect_holiday_names(raw_text):
            if holiday_name not in holiday_names:
                holiday_names.append(holiday_name)

        parsed["must_include_holiday_names"] = holiday_names

    if not parsed.get("departure_airport"):
        parsed["departure_airport"] = "ICN"

    target_year = _get_target_year(parsed)

    must_include_dates = _coerce_list(parsed.get("must_include_dates"))
    must_include_holiday_names = _coerce_list(parsed.get("must_include_holiday_names"))

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

    for holiday_date in csv_dates + fallback_dates:
        if holiday_date not in must_include_dates:
            must_include_dates.append(holiday_date)

    parsed["must_include_dates"] = sorted(set(must_include_dates))
    parsed["must_include_holiday_names"] = sorted(set(must_include_holiday_names))

    return parsed


def _date_range_matches_required_dates(
    departure_date,
    return_date,
    required_dates: List[str],
) -> bool:
    if not required_dates:
        return True

    departure_date = _parse_date(departure_date)
    return_date = _parse_date(return_date)

    if not departure_date or not return_date:
        return False

    for required_date in required_dates:
        required = _parse_date(required_date)

        if required is None:
            continue

        if departure_date <= required <= return_date:
            return True

    return False


def generate_date_candidates(parsed_request: Dict[str, Any]) -> List[Dict[str, str]]:
    parsed_request = complete_parsed_request(parsed_request)

    preferred_departure_date = parsed_request.get("preferred_departure_date")
    preferred_return_date = parsed_request.get("preferred_return_date")
    required_dates = _coerce_list(parsed_request.get("must_include_dates"))
    nights = parsed_request.get("nights")

    if nights is None:
        raise ValueError(f"체류 기간을 찾지 못했습니다. 예: 3박4일 / 추출 결과: {parsed_request}")

    if preferred_departure_date and preferred_return_date:
        if not _date_range_matches_required_dates(
            preferred_departure_date,
            preferred_return_date,
            required_dates,
        ):
            raise ValueError("지정한 출도착 일정에 포함 조건이 반영되지 않습니다.")

        return [
            {
                "departure_date": preferred_departure_date,
                "return_date": preferred_return_date,
            }
        ]

    travel_window_start = parsed_request.get("travel_window_start")
    travel_window_end = parsed_request.get("travel_window_end")

    candidates = []

    if travel_window_start and travel_window_end:
        start_date = pd.to_datetime(travel_window_start).date()
        end_date = pd.to_datetime(travel_window_end).date()
        current_departure = start_date

        while current_departure + timedelta(days=int(nights)) <= end_date:
            return_date = current_departure + timedelta(days=int(nights))

            candidate = {
                "departure_date": str(current_departure),
                "return_date": str(return_date),
            }

            if _date_range_matches_required_dates(
                candidate["departure_date"],
                candidate["return_date"],
                required_dates,
            ):
                candidates.append(candidate)

            current_departure += timedelta(days=1)

    elif required_dates:
        parsed_required_dates = sorted(
            [
                _parse_date(required_date)
                for required_date in required_dates
                if _parse_date(required_date)
            ]
        )

        if not parsed_required_dates:
            raise ValueError(f"포함 조건 날짜를 해석하지 못했습니다. 추출 결과: {parsed_request}")

        first_required_date = parsed_required_dates[0]
        last_required_date = parsed_required_dates[-1]

        earliest_departure = first_required_date - timedelta(days=int(nights))
        latest_departure = last_required_date

        current_departure = earliest_departure

        while current_departure <= latest_departure:
            return_date = current_departure + timedelta(days=int(nights))

            candidate = {
                "departure_date": str(current_departure),
                "return_date": str(return_date),
            }

            if _date_range_matches_required_dates(
                candidate["departure_date"],
                candidate["return_date"],
                required_dates,
            ):
                candidates.append(candidate)

            current_departure += timedelta(days=1)

    else:
        raise ValueError(f"여행 가능 기간 또는 공휴일 기준 조건을 찾지 못했습니다. 추출 결과: {parsed_request}")

    if not candidates:
        raise ValueError(
            f"입력 조건 안에서 포함 조건 {required_dates}를 만족하는 일정을 만들 수 없습니다."
        )

    unique_candidates = []
    seen = set()

    for candidate in candidates:
        key = (candidate["departure_date"], candidate["return_date"])

        if key in seen:
            continue

        seen.add(key)
        unique_candidates.append(candidate)

    return unique_candidates


def filter_destination_airports(
    df: pd.DataFrame,
    departure_airport: str,
    parsed_request: Dict[str, Any],
) -> List[str]:
    parsed_request = complete_parsed_request(parsed_request)

    available_arrivals = (
        df[df["departure_airport"] == departure_airport]["arrival_airport"]
        .dropna()
        .unique()
        .tolist()
    )

    destination_city = parsed_request.get("destination_city")
    destination_country = parsed_request.get("destination_country")

    if destination_city:
        city_airports = CITY_TO_AIRPORT.get(destination_city, [])
        matched = [airport for airport in available_arrivals if airport in city_airports]

        if matched:
            return matched

    if destination_country == "일본":
        return sorted(available_arrivals)

    return sorted(available_arrivals)


def build_sample_input(matched_feature: Dict[str, Any], departure_date: str) -> Dict[str, Any]:
    return {
        **matched_feature,
        "departure_airport": matched_feature.get("departure_airport"),
        "arrival_airport": matched_feature.get("arrival_airport"),
        "departure_date": departure_date,
        "passenger_growth_rate": matched_feature.get("passenger_growth_rate", 0),
        "flight_growth_rate": matched_feature.get("flight_growth_rate", 0),
        "days_to_holiday": matched_feature.get("days_to_holiday", 0),
        "holiday_name": matched_feature.get("holiday_name", ""),
        "holiday_count": matched_feature.get("holiday_count", 0),
        "jpy_krw_change_rate": matched_feature.get("jpy_krw_change_rate", 0),
        "delay_rate": matched_feature.get("delay_rate", 0),
        "cancel_count": matched_feature.get("cancel_count", 0),
        "avg_carrier_count": matched_feature.get("avg_carrier_count", 0),
        "avg_lcc_share": matched_feature.get("avg_lcc_share", 0),
    }


def _select_diverse_recommendations(
    results: List[Dict[str, Any]],
    recommendation_count: int,
) -> List[Dict[str, Any]]:
    sorted_results = sorted(
        results,
        key=lambda item: item.get("risk_score") if item.get("risk_score") is not None else -1,
        reverse=True,
    )

    selected = []
    used_routes = set()

    for item in sorted_results:
        route_key = (
            item.get("departure_airport"),
            item.get("arrival_airport"),
        )

        if route_key in used_routes:
            continue

        selected.append(item)
        used_routes.add(route_key)

        if len(selected) >= recommendation_count:
            break

    if len(selected) < recommendation_count:
        used_items = {
            (
                item.get("departure_airport"),
                item.get("arrival_airport"),
                item.get("departure_date"),
                item.get("return_date"),
            )
            for item in selected
        }

        for item in sorted_results:
            item_key = (
                item.get("departure_airport"),
                item.get("arrival_airport"),
                item.get("departure_date"),
                item.get("return_date"),
            )

            if item_key in used_items:
                continue

            selected.append(item)
            used_items.add(item_key)

            if len(selected) >= recommendation_count:
                break

    return selected


def recommend_routes_from_request(
    df: pd.DataFrame,
    parsed_request: Dict[str, Any],
) -> List[Dict[str, Any]]:
    parsed_request = complete_parsed_request(parsed_request)

    departure_airport = parsed_request.get("departure_airport") or "ICN"
    recommendation_count = int(parsed_request.get("recommendation_count") or 5)

    date_candidates = generate_date_candidates(parsed_request)
    arrival_airports = filter_destination_airports(
        df=df,
        departure_airport=departure_airport,
        parsed_request=parsed_request,
    )

    results = []

    available_years = sorted(df["year"].dropna().astype(int).unique().tolist())

    for date_candidate in date_candidates:
        departure_date = date_candidate["departure_date"]
        return_date = date_candidate["return_date"]
        target_year = pd.to_datetime(departure_date).year

        if target_year in available_years:
            analysis_year = target_year
        else:
            past_years = [year for year in available_years if year <= target_year]
            analysis_year = max(past_years) if past_years else max(available_years)

        for arrival_airport in arrival_airports:
            try:
                matched_feature = find_route_feature(
                    df=df,
                    departure_airport=departure_airport,
                    arrival_airport=arrival_airport,
                    departure_date=departure_date,
                    year=analysis_year,
                )

                sample_input = build_sample_input(
                    matched_feature=matched_feature,
                    departure_date=departure_date,
                )

                risk_result = run_agent_pipeline(sample_input)

                results.append(
                    {
                        "departure_airport": risk_result.get("departure_airport"),
                        "arrival_airport": risk_result.get("arrival_airport"),
                        "departure_date": departure_date,
                        "return_date": return_date,
                        "risk_level": risk_result.get("risk_level"),
                        "risk_score": risk_result.get("risk_score"),
                        "purchase_timing_recommendation": risk_result.get(
                            "purchase_timing_recommendation"
                        ),
                        "decision_reason": risk_result.get("decision_reason"),
                        "required_include_dates": parsed_request.get("must_include_dates") or [],
                        "risk_result": risk_result,
                        "matched_feature": matched_feature,
                    }
                )

            except Exception:
                continue

    if not results:
        raise ValueError("조건에 맞는 추천 후보를 만들 수 없습니다.")

    return _select_diverse_recommendations(
        results=results,
        recommendation_count=recommendation_count,
    )