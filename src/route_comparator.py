from typing import List, Dict, Any, Optional

import pandas as pd

from src.agents import run_agent_pipeline


def _select_feature_for_destination(
    route_df: pd.DataFrame,
    requested_date: str
) -> Optional[Dict[str, Any]]:
    exact_match = route_df[
        route_df["departure_date"].astype(str) == str(requested_date)
    ]

    if not exact_match.empty:
        feature = exact_match.iloc[0].to_dict()
        feature["requested_departure_date"] = str(requested_date)
        feature["source_departure_date"] = str(feature["departure_date"])
        feature["data_match_type"] = "exact"
        return feature

    temp_df = route_df.copy()
    temp_df["_parsed_departure_date"] = pd.to_datetime(
        temp_df["departure_date"],
        errors="coerce"
    )

    requested_dt = pd.to_datetime(requested_date, errors="coerce")

    if pd.isna(requested_dt) or temp_df["_parsed_departure_date"].isna().all():
        selected = temp_df.iloc[0].drop(labels=["_parsed_departure_date"]).to_dict()
    else:
        temp_df["_date_diff"] = (
            temp_df["_parsed_departure_date"] - requested_dt
        ).abs()

        selected = (
            temp_df.sort_values("_date_diff")
            .iloc[0]
            .drop(labels=["_parsed_departure_date", "_date_diff"])
            .to_dict()
        )

    selected["requested_departure_date"] = str(requested_date)
    selected["source_departure_date"] = str(selected["departure_date"])
    selected["departure_date"] = str(requested_date)
    selected["data_match_type"] = "nearest_fallback"

    return selected


def compare_routes_by_destination(
    df: pd.DataFrame,
    original_text: str,
    departure_airport: str,
    departure_date: str,
    route_name_builder
) -> List[Dict[str, Any]]:
    """
    같은 출발공항과 같은 출발일 기준으로 목적지별 구매 위험도를 비교한다.
    샘플 데이터에 정확한 출발일이 없으면 같은 노선의 가까운 샘플 데이터를 참고하되,
    분석 기준일은 사용자가 요청한 departure_date로 유지한다.
    """

    departure_date = str(departure_date)

    departure_df = df[
        df["departure_airport"] == departure_airport
    ].copy()

    if departure_df.empty:
        return []

    comparison_results = []

    for arrival_airport, route_df in departure_df.groupby("arrival_airport"):
        feature = _select_feature_for_destination(route_df, departure_date)

        if not feature:
            continue

        route_name = route_name_builder(
            feature["departure_airport"],
            feature["arrival_airport"]
        )

        agent_input = {
            "original_text": original_text,
            "departure_airport": feature["departure_airport"],
            "arrival_airport": feature["arrival_airport"],
            "route_name": route_name,
            "departure_date": str(feature["departure_date"]),
            "passenger_growth_rate": float(feature["passenger_growth_rate"]),
            "flight_growth_rate": float(feature["flight_growth_rate"]),
            "days_to_holiday": int(feature["days_to_holiday"]),
            "holiday_name": str(feature["holiday_name"]),
            "jpy_krw_change_rate": float(feature["jpy_krw_change_rate"]),
            "delay_rate": float(feature["delay_rate"]),
            "cancel_count": int(feature["cancel_count"]),
        }

        risk_result = run_agent_pipeline(agent_input)
        risk = risk_result["risk_assessment"]

        comparison_results.append(
            {
                "route_name": route_name,
                "departure_airport": feature["departure_airport"],
                "arrival_airport": feature["arrival_airport"],
                "departure_date": str(feature["departure_date"]),
                "source_departure_date": str(feature.get("source_departure_date")),
                "data_match_type": feature.get("data_match_type"),
                "risk_level": risk["risk_level"],
                "risk_score": risk["risk_score"],
                "max_score": risk["max_score"],
                "recommendation": risk["recommendation"],
                "confidence": risk["confidence"],
                "passenger_growth_rate": float(feature["passenger_growth_rate"]),
                "flight_growth_rate": float(feature["flight_growth_rate"]),
                "days_to_holiday": int(feature["days_to_holiday"]),
            }
        )

    comparison_results = sorted(
        comparison_results,
        key=lambda item: item["risk_score"]
    )

    return comparison_results


def get_best_route(comparison_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not comparison_results:
        return None

    return min(
        comparison_results,
        key=lambda item: item["risk_score"]
    )