from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd


DATA_PATH = Path("data/sample_route_features.csv")


def load_sample_route_features() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            "data/sample_route_features.csv 파일을 찾을 수 없습니다."
        )

    df = pd.read_csv(DATA_PATH)

    required_columns = [
        "route",
        "departure_airport",
        "arrival_airport",
        "departure_date",
        "passenger_growth_rate",
        "flight_growth_rate",
        "days_to_holiday",
        "holiday_name",
        "jpy_krw_change_rate",
        "delay_rate",
        "cancel_count",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"샘플 데이터에 필요한 컬럼이 없습니다: {missing_columns}"
        )

    return df


def find_route_feature(
    df: pd.DataFrame,
    departure_airport: str,
    arrival_airport: str,
    departure_date: str
) -> Optional[Dict[str, Any]]:
    exact_match = df[
        (df["departure_airport"] == departure_airport)
        & (df["arrival_airport"] == arrival_airport)
        & (df["departure_date"] == departure_date)
    ]

    if not exact_match.empty:
        return exact_match.iloc[0].to_dict()

    route_match = df[
        (df["departure_airport"] == departure_airport)
        & (df["arrival_airport"] == arrival_airport)
    ]

    if not route_match.empty:
        return route_match.iloc[0].to_dict()

    return None


def get_available_routes(df: pd.DataFrame) -> list[dict]:
    route_df = df[
        ["route", "departure_airport", "arrival_airport"]
    ].drop_duplicates()

    return route_df.to_dict(orient="records")