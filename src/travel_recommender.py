from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from src.agents import run_agent_pipeline
from src.data_loader import find_route_feature, normalize_airport_code


DEFAULT_DEPARTURE_AIRPORT = "ICN"
DEFAULT_DESTINATION_COUNTRY = "일본"
DEFAULT_RECOMMENDATION_COUNT = 5
MAX_DATE_CANDIDATES = 40


JAPAN_CITY_TO_AIRPORT_CODES = {
    "도쿄": ["NRT", "HND"],
    "나리타": ["NRT"],
    "하네다": ["HND"],
    "오사카": ["KIX"],
    "간사이": ["KIX"],
    "후쿠오카": ["FUK"],
    "삿포로": ["CTS"],
    "치토세": ["CTS"],
    "오키나와": ["OKA"],
    "오끼나와": ["OKA"],
    "나고야": ["NGO"],
    "고베": ["UKB"],
    "구마모토": ["KMJ"],
    "구마모도": ["KMJ"],
    "히로시마": ["HIJ"],
    "센다이": ["SDJ"],
    "아오모리": ["AOJ"],
    "시즈오카": ["FSZ"],
    "요나고": ["YGJ"],
}


HOLIDAY_FALLBACK_DATES = {
    2027: {
        "설날": ["2027-02-06", "2027-02-07", "2027-02-08"],
        "추석": ["2027-09-14", "2027-09-15", "2027-09-16"],
        "크리스마스": ["2027-12-25"],
    },
    2026: {
        "설날": ["2026-02-16", "2026-02-17", "2026-02-18"],
        "추석": ["2026-09-24", "2026-09-25", "2026-09-26"],
        "크리스마스": ["2026-12-25"],
    },
}


def _safe_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _parse_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except Exception:
        return None


def _format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return list(value)

    return [value]


def _extract_year(parsed_request: Dict[str, Any]) -> int:
    year_candidates = [
        parsed_request.get("year"),
        parsed_request.get("travel_year"),
        parsed_request.get("target_year"),
    ]

    for value in year_candidates:
        parsed_year = _safe_int(value, 0)

        if parsed_year > 0:
            return parsed_year

    today = datetime.today()

    text_candidates = [
        parsed_request.get("text"),
        parsed_request.get("raw_text"),
        parsed_request.get("original_text"),
        parsed_request.get("user_text"),
        parsed_request.get("raw_user_text"),
        parsed_request.get("travel_period"),
        parsed_request.get("date_text"),
    ]

    joined_text = " ".join([_safe_str(value) for value in text_candidates])

    if "내년" in joined_text:
        return today.year + 1

    if "올해" in joined_text:
        return today.year

    return today.year


def _extract_trip_days(parsed_request: Dict[str, Any]) -> int:
    candidates = [
        parsed_request.get("trip_days"),
        parsed_request.get("travel_days"),
        parsed_request.get("duration_days"),
        parsed_request.get("stay_days"),
        parsed_request.get("days"),
    ]

    for value in candidates:
        parsed_value = _safe_int(value, 0)

        if parsed_value > 0:
            return parsed_value

    night_candidates = [
        parsed_request.get("trip_nights"),
        parsed_request.get("nights"),
        parsed_request.get("stay_nights"),
    ]

    for value in night_candidates:
        parsed_value = _safe_int(value, 0)

        if parsed_value > 0:
            return parsed_value + 1

    text_candidates = [
        parsed_request.get("text"),
        parsed_request.get("raw_text"),
        parsed_request.get("original_text"),
        parsed_request.get("user_text"),
        parsed_request.get("raw_user_text"),
    ]

    joined_text = " ".join([_safe_str(value) for value in text_candidates])

    if "3박4일" in joined_text or "3박 4일" in joined_text:
        return 4

    if "2박3일" in joined_text or "2박 3일" in joined_text:
        return 3

    if "4박5일" in joined_text or "4박 5일" in joined_text:
        return 5

    return 4


def _extract_holiday_names(parsed_request: Dict[str, Any]) -> List[str]:
    names = []

    for key in [
        "must_include_holiday_names",
        "holiday_names",
        "target_holidays",
        "holidays",
    ]:
        for value in _as_list(parsed_request.get(key)):
            text = _safe_str(value)

            if text:
                names.append(text)

    text_candidates = [
        parsed_request.get("text"),
        parsed_request.get("raw_text"),
        parsed_request.get("original_text"),
        parsed_request.get("user_text"),
        parsed_request.get("raw_user_text"),
        parsed_request.get("travel_period"),
        parsed_request.get("date_text"),
    ]

    joined_text = " ".join([_safe_str(value) for value in text_candidates])

    for holiday_name in ["추석", "설날", "크리스마스"]:
        if holiday_name in joined_text:
            names.append(holiday_name)

    result = []

    for name in names:
        if name not in result:
            result.append(name)

    return result


def _extract_required_dates(parsed_request: Dict[str, Any], year: int) -> List[str]:
    dates = []

    for key in [
        "required_include_dates",
        "must_include_dates",
        "include_dates",
        "holiday_dates",
    ]:
        for value in _as_list(parsed_request.get(key)):
            parsed_date = _parse_date(value)

            if parsed_date:
                dates.append(_format_date(parsed_date))

    if dates:
        return sorted(list(set(dates)))

    holiday_names = _extract_holiday_names(parsed_request)

    for holiday_name in holiday_names:
        fallback_dates = HOLIDAY_FALLBACK_DATES.get(year, {}).get(holiday_name, [])

        for fallback_date in fallback_dates:
            dates.append(fallback_date)

    return sorted(list(set(dates)))


def _extract_date_window(
    parsed_request: Dict[str, Any],
    trip_days: int,
    required_dates: List[str],
    year: int,
) -> Dict[str, str]:
    start_candidates = [
        parsed_request.get("earliest_departure_date"),
        parsed_request.get("start_date"),
        parsed_request.get("departure_start_date"),
        parsed_request.get("min_departure_date"),
        parsed_request.get("travel_window_start"),
        parsed_request.get("preferred_departure_date"),
    ]

    end_candidates = [
        parsed_request.get("latest_departure_date"),
        parsed_request.get("end_date"),
        parsed_request.get("departure_end_date"),
        parsed_request.get("max_departure_date"),
        parsed_request.get("travel_window_end"),
        parsed_request.get("preferred_return_date"),
    ]

    start_date = None
    end_date = None

    for value in start_candidates:
        start_date = _parse_date(value)

        if start_date:
            break

    for value in end_candidates:
        end_date = _parse_date(value)

        if end_date:
            break

    if required_dates:
        parsed_required_dates = [_parse_date(value) for value in required_dates]
        parsed_required_dates = [value for value in parsed_required_dates if value]

        if parsed_required_dates:
            first_required_date = min(parsed_required_dates)
            last_required_date = max(parsed_required_dates)

            required_start = first_required_date - timedelta(days=trip_days - 1)
            required_end = last_required_date

            if start_date is None:
                start_date = required_start

            if end_date is None:
                end_date = required_end

    if start_date is None:
        start_date = datetime(year, 1, 1)

    if end_date is None:
        end_date = datetime(year, 12, 31)

    if end_date < start_date:
        end_date = start_date

    return {
        "earliest_departure_date": _format_date(start_date),
        "latest_departure_date": _format_date(end_date),
    }


def complete_parsed_request(parsed_request: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(parsed_request or {})

    year = _extract_year(result)
    trip_days = _extract_trip_days(result)
    required_dates = _extract_required_dates(result, year)
    holiday_names = _extract_holiday_names(result)

    date_window = _extract_date_window(
        parsed_request=result,
        trip_days=trip_days,
        required_dates=required_dates,
        year=year,
    )

    result["year"] = year
    result["trip_days"] = trip_days
    result["travel_days"] = trip_days
    result["departure_airport"] = normalize_airport_code(
        result.get("departure_airport")
        or result.get("origin_airport")
        or result.get("origin")
        or DEFAULT_DEPARTURE_AIRPORT
    )
    result["destination_country"] = (
        result.get("destination_country")
        or result.get("country")
        or DEFAULT_DESTINATION_COUNTRY
    )
    result["must_include_dates"] = required_dates
    result["required_include_dates"] = required_dates
    result["must_include_holiday_names"] = holiday_names
    result.update(date_window)

    return result


def _count_required_dates_in_range(
    departure_date: datetime,
    return_date: datetime,
    required_dates: List[str],
) -> int:
    if not required_dates:
        return 0

    count = 0

    for value in required_dates:
        parsed_required_date = _parse_date(value)

        if parsed_required_date and departure_date <= parsed_required_date <= return_date:
            count += 1

    return count


def _date_range_matches_required_dates(
    departure_date: datetime,
    return_date: datetime,
    required_dates: List[str],
) -> bool:
    if not required_dates:
        return True

    return _count_required_dates_in_range(
        departure_date=departure_date,
        return_date=return_date,
        required_dates=required_dates,
    ) > 0


def _generate_candidate_dates(parsed_request: Dict[str, Any]) -> List[Dict[str, Any]]:
    trip_days = _safe_int(parsed_request.get("trip_days"), 4)
    trip_days = max(trip_days, 1)

    start_date = _parse_date(parsed_request.get("earliest_departure_date"))
    end_date = _parse_date(parsed_request.get("latest_departure_date"))

    if start_date is None:
        start_date = datetime(_extract_year(parsed_request), 1, 1)

    if end_date is None:
        end_date = datetime(_extract_year(parsed_request), 12, 31)

    required_dates = (
        parsed_request.get("required_include_dates")
        or parsed_request.get("must_include_dates")
        or []
    )

    candidates = []
    current_date = start_date

    while current_date <= end_date:
        return_date = current_date + timedelta(days=trip_days - 1)

        required_date_match_count = _count_required_dates_in_range(
            departure_date=current_date,
            return_date=return_date,
            required_dates=required_dates,
        )

        if not required_dates or required_date_match_count > 0:
            candidates.append(
                {
                    "departure_date": _format_date(current_date),
                    "return_date": _format_date(return_date),
                    "required_date_match_count": required_date_match_count,
                }
            )

        current_date += timedelta(days=1)

    candidates = sorted(
        candidates,
        key=lambda item: (
            -item.get("required_date_match_count", 0),
            item.get("departure_date", ""),
        ),
    )

    if len(candidates) <= MAX_DATE_CANDIDATES:
        return candidates

    step = max(len(candidates) // MAX_DATE_CANDIDATES, 1)
    sampled_candidates = candidates[::step][:MAX_DATE_CANDIDATES]

    return sampled_candidates


def _extract_destination_airport_codes(parsed_request: Dict[str, Any]) -> List[str]:
    codes = []

    for key in [
        "arrival_airport",
        "destination_airport",
        "arrival_airport_code",
        "destination_airport_code",
    ]:
        value = parsed_request.get(key)

        if value:
            codes.append(normalize_airport_code(value))

    keyword_values = []

    for key in [
        "destination",
        "destination_city",
        "city",
        "travel_destination",
        "destination_keywords",
        "keywords",
    ]:
        keyword_values.extend(_as_list(parsed_request.get(key)))

    text_candidates = [
        parsed_request.get("text"),
        parsed_request.get("raw_text"),
        parsed_request.get("original_text"),
        parsed_request.get("user_text"),
        parsed_request.get("raw_user_text"),
    ]

    keyword_values.extend(text_candidates)

    joined_text = " ".join([_safe_str(value) for value in keyword_values])

    for city_name, airport_codes in JAPAN_CITY_TO_AIRPORT_CODES.items():
        if city_name in joined_text:
            codes.extend(airport_codes)

    result = []

    for code in codes:
        code = normalize_airport_code(code)

        if code and code not in result:
            result.append(code)

    return result


def _filter_candidate_routes(
    df: pd.DataFrame,
    parsed_request: Dict[str, Any],
) -> pd.DataFrame:
    departure_airport = normalize_airport_code(
        parsed_request.get("departure_airport") or DEFAULT_DEPARTURE_AIRPORT
    )

    route_df = df[df["departure_airport"] == departure_airport].copy()

    destination_codes = _extract_destination_airport_codes(parsed_request)

    if destination_codes:
        route_df = route_df[route_df["arrival_airport"].isin(destination_codes)].copy()

    if route_df.empty:
        return route_df

    return (
        route_df
        .sort_values(["year", "normalized_base_risk_score"], ascending=[False, False])
        .drop_duplicates(subset=["departure_airport", "arrival_airport"])
        .copy()
    )


def _build_sample_input(
    matched_feature: Dict[str, Any],
    departure_date: str,
    return_date: Optional[str],
    parsed_request: Dict[str, Any],
) -> Dict[str, Any]:
    sample_input = dict(matched_feature)

    sample_input["departure_date"] = departure_date

    if return_date:
        sample_input["return_date"] = return_date

    sample_input["required_include_dates"] = (
        parsed_request.get("required_include_dates")
        or parsed_request.get("must_include_dates")
        or []
    )
    sample_input["must_include_dates"] = sample_input["required_include_dates"]
    sample_input["must_include_holiday_names"] = (
        parsed_request.get("must_include_holiday_names")
        or []
    )

    if sample_input["must_include_holiday_names"]:
        sample_input["holiday_name"] = ", ".join(sample_input["must_include_holiday_names"])
        sample_input["holiday_count"] = max(
            len(sample_input["required_include_dates"]),
            1,
        )

    return sample_input


def _build_recommendation_item(
    route_feature: Dict[str, Any],
    risk_result: Dict[str, Any],
    departure_date: str,
    return_date: str,
    trip_days: int,
    required_date_match_count: int,
) -> Dict[str, Any]:
    return {
        "route": route_feature.get("route"),
        "route_name": route_feature.get("route_name") or route_feature.get("route"),
        "departure_airport": route_feature.get("departure_airport"),
        "arrival_airport": route_feature.get("arrival_airport"),
        "departure_date": departure_date,
        "return_date": return_date,
        "trip_days": trip_days,
        "required_date_match_count": required_date_match_count,
        "risk_score": risk_result.get("risk_score"),
        "risk_level": risk_result.get("risk_level"),
        "purchase_timing_recommendation": risk_result.get("purchase_timing_recommendation"),
        "decision_reason": risk_result.get("decision_reason"),
        "reason": risk_result.get("decision_reason"),
        "factor_scores": risk_result.get("factor_scores"),
        "risk_method": risk_result.get("risk_method"),
        "risk_score_description": risk_result.get("risk_score_description"),
        "risk_result": risk_result,
        "matched_feature": route_feature,
    }


def _is_better_recommendation(
    candidate_item: Dict[str, Any],
    current_best_item: Dict[str, Any],
) -> bool:
    candidate_score = candidate_item.get("risk_score") or 0
    current_score = current_best_item.get("risk_score") or 0

    if candidate_score != current_score:
        return candidate_score > current_score

    candidate_match_count = candidate_item.get("required_date_match_count") or 0
    current_match_count = current_best_item.get("required_date_match_count") or 0

    if candidate_match_count != current_match_count:
        return candidate_match_count > current_match_count

    return str(candidate_item.get("departure_date")) < str(current_best_item.get("departure_date"))


def recommend_routes_from_request(
    df: pd.DataFrame,
    parsed_request: Dict[str, Any],
    recommendation_count: int = DEFAULT_RECOMMENDATION_COUNT,
) -> List[Dict[str, Any]]:
    parsed_request = complete_parsed_request(parsed_request)

    candidate_routes = _filter_candidate_routes(
        df=df,
        parsed_request=parsed_request,
    )

    if candidate_routes.empty:
        raise ValueError("입력 조건에 맞는 후보 노선을 찾을 수 없습니다.")

    candidate_dates = _generate_candidate_dates(parsed_request)

    if not candidate_dates:
        raise ValueError("입력 조건에 맞는 여행 날짜 조합을 만들 수 없습니다.")

    trip_days = _safe_int(parsed_request.get("trip_days"), 4)
    recommendations = []

    for _, route_row in candidate_routes.iterrows():
        departure_airport = route_row.get("departure_airport")
        arrival_airport = route_row.get("arrival_airport")

        best_route_item = None

        for date_candidate in candidate_dates:
            departure_date = date_candidate["departure_date"]
            return_date = date_candidate["return_date"]
            required_date_match_count = _safe_int(
                date_candidate.get("required_date_match_count"),
                0,
            )

            route_feature = find_route_feature(
                df=df,
                departure_airport=departure_airport,
                arrival_airport=arrival_airport,
                departure_date=departure_date,
            )

            sample_input = _build_sample_input(
                matched_feature=route_feature,
                departure_date=departure_date,
                return_date=return_date,
                parsed_request=parsed_request,
            )

            risk_result = run_agent_pipeline(sample_input)

            item = _build_recommendation_item(
                route_feature=route_feature,
                risk_result=risk_result,
                departure_date=departure_date,
                return_date=return_date,
                trip_days=trip_days,
                required_date_match_count=required_date_match_count,
            )

            if best_route_item is None:
                best_route_item = item
                continue

            if _is_better_recommendation(
                candidate_item=item,
                current_best_item=best_route_item,
            ):
                best_route_item = item

        if best_route_item:
            recommendations.append(best_route_item)

    recommendations = sorted(
        recommendations,
        key=lambda item: (
            item.get("risk_score") or 0,
            item.get("required_date_match_count") or 0,
        ),
        reverse=True,
    )

    for index, item in enumerate(recommendations, start=1):
        item["rank"] = index
        item["recommendation_rank"] = index

    return recommendations[:recommendation_count]