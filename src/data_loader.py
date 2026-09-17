from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd


DATA_PATH = Path("data/sample_route_features.csv")


REQUIRED_COLUMNS = [
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


def load_sample_route_features() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            "data/sample_route_features.csv 파일을 찾을 수 없습니다."
        )

    df = pd.read_csv(DATA_PATH)

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"샘플 데이터에 필요한 컬럼이 없습니다: {missing_columns}"
        )

    df["departure_date"] = df["departure_date"].astype(str)

    return df


def _choose_nearest_date_row(
    route_df: pd.DataFrame,
    requested_date: str
) -> Dict[str, Any]:
    temp_df = route_df.copy()

    temp_df["_parsed_departure_date"] = pd.to_datetime(
        temp_df["departure_date"],
        errors="coerce"
    )

    requested_dt = pd.to_datetime(requested_date, errors="coerce")

    if pd.isna(requested_dt) or temp_df["_parsed_departure_date"].isna().all():
        selected_row = temp_df.iloc[0].drop(labels=["_parsed_departure_date"]).to_dict()
        return selected_row

    temp_df["_date_diff"] = (
        temp_df["_parsed_departure_date"] - requested_dt
    ).abs()

    selected_row = (
        temp_df.sort_values("_date_diff")
        .iloc[0]
        .drop(labels=["_parsed_departure_date", "_date_diff"])
        .to_dict()
    )

    return selected_row


def find_route_feature(
    df: pd.DataFrame,
    departure_airport: str,
    arrival_airport: str,
    departure_date: str
) -> Optional[Dict[str, Any]]:
    requested_date = str(departure_date)

    exact_match = df[
        (df["departure_airport"] == departure_airport)
        & (df["arrival_airport"] == arrival_airport)
        & (df["departure_date"] == requested_date)
    ]

    if not exact_match.empty:
        feature = exact_match.iloc[0].to_dict()
        feature["requested_departure_date"] = requested_date
        feature["source_departure_date"] = str(feature["departure_date"])
        feature["data_match_type"] = "exact"
        return feature

    route_match = df[
        (df["departure_airport"] == departure_airport)
        & (df["arrival_airport"] == arrival_airport)
    ]

    if not route_match.empty:
        feature = _choose_nearest_date_row(route_match, requested_date)
        feature["requested_departure_date"] = requested_date
        feature["source_departure_date"] = str(feature["departure_date"])
        feature["departure_date"] = requested_date
        feature["data_match_type"] = "route_fallback"
        return feature

    return None


def get_available_routes(df: pd.DataFrame) -> list[dict]:
    route_df = df[
        ["route", "departure_airport", "arrival_airport"]
    ].drop_duplicates()

    return route_df.to_dict(orient="records")