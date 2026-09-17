from typing import List, Dict, Any

import pandas as pd

from src.agents import run_agent_pipeline


def compare_routes_by_destination(
    df: pd.DataFrame,
    original_text: str,
    departure_airport: str,
    departure_date: str,
    route_name_builder
) -> List[Dict[str, Any]]:
    """
    같은 출발공항과 출발일 기준으로 도착지별 구매 위험도를 비교한다.
    """

    same_date_routes = df[
        (df["departure_airport"] == departure_airport)
        & (df["departure_date"] == departure_date)
    ]

    if same_date_routes.empty:
        same_date_routes = df[
            df["departure_airport"] == departure_airport
        ]

    comparison_results = []

    for _, row in same_date_routes.iterrows():
        route_name = route_name_builder(
            row["departure_airport"],
            row["arrival_airport"]
        )

        agent_input = {
            "original_text": original_text,
            "departure_airport": row["departure_airport"],
            "arrival_airport": row["arrival_airport"],
            "route_name": route_name,
            "departure_date": str(row["departure_date"]),
            "passenger_growth_rate": float(row["passenger_growth_rate"]),
            "flight_growth_rate": float(row["flight_growth_rate"]),
            "days_to_holiday": int(row["days_to_holiday"]),
            "holiday_name": str(row["holiday_name"]),
            "jpy_krw_change_rate": float(row["jpy_krw_change_rate"]),
            "delay_rate": float(row["delay_rate"]),
            "cancel_count": int(row["cancel_count"]),
        }

        risk_result = run_agent_pipeline(agent_input)
        risk = risk_result["risk_assessment"]

        comparison_results.append(
            {
                "route_name": route_name,
                "departure_airport": row["departure_airport"],
                "arrival_airport": row["arrival_airport"],
                "departure_date": str(row["departure_date"]),
                "risk_level": risk["risk_level"],
                "risk_score": risk["risk_score"],
                "max_score": risk["max_score"],
                "recommendation": risk["recommendation"],
                "confidence": risk["confidence"],
                "passenger_growth_rate": float(row["passenger_growth_rate"]),
                "flight_growth_rate": float(row["flight_growth_rate"]),
                "days_to_holiday": int(row["days_to_holiday"]),
            }
        )

    comparison_results = sorted(
        comparison_results,
        key=lambda item: item["risk_score"]
    )

    return comparison_results


def get_best_route(comparison_results: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not comparison_results:
        return None

    return min(
        comparison_results,
        key=lambda item: item["risk_score"]
    )