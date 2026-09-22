from pathlib import Path
from typing import Optional
import pandas as pd

DATA_PATH = Path("data/processed/route_features_japan.csv")


def load_route_features() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} 파일이 없습니다. 먼저 scripts/build_route_features.py를 실행하세요."
        )

    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")

    required_cols = [
        "year",
        "route",
        "origin",
        "destination",
        "passenger_growth_rate",
        "flight_growth_rate",
        "passengers_per_flight",
        "risk_score",
        "risk_level",
        "purchase_timing_recommendation",
    ]

    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"route_features_japan.csv 누락 컬럼: {missing_cols}")

    # 기존 app.py 호환용 컬럼 생성
    df["departure_airport"] = df["origin"]
    df["arrival_airport"] = df["destination"]
    df["departure_date"] = df["year"].astype(str) + "-01-01"

    # 기존 app.py가 사용할 수 있는 별칭 컬럼
    df["route_name"] = df["route"]
    df["recommendation"] = df["purchase_timing_recommendation"]

    # 혹시 app.py에서 기대하는 기본 컬럼이 없을 경우 대비
    if "delay_rate" not in df.columns:
        df["delay_rate"] = 0

    if "cancel_count" not in df.columns:
        df["cancel_count"] = 0

    if "days_to_holiday" not in df.columns:
        df["days_to_holiday"] = 0

    if "holiday_name" not in df.columns:
        df["holiday_name"] = df.get("holiday_names", "")

    if "jpy_krw_change_rate" not in df.columns:
        if "jpy_krw_change_rate_30d" in df.columns:
            df["jpy_krw_change_rate"] = df["jpy_krw_change_rate_30d"]
        else:
            df["jpy_krw_change_rate"] = 0

    return df


def get_available_routes() -> list:
    df = load_route_features()

    routes = (
        df[["route", "origin", "destination"]]
        .drop_duplicates()
        .sort_values("route")
    )

    return routes.to_dict("records")


def get_available_years() -> list:
    df = load_route_features()

    years = sorted(df["year"].dropna().astype(int).unique().tolist())

    return years


def get_route_feature(route: str, year: Optional[int] = None) -> dict:
    df = load_route_features()

    route_df = df[df["route"] == route].copy()

    if route_df.empty:
        available_routes = df["route"].drop_duplicates().head(20).tolist()
        raise ValueError(
            f"선택한 노선을 찾을 수 없습니다: {route}. "
            f"사용 가능한 예시 노선: {available_routes}"
        )

    if year is not None:
        matched = route_df[route_df["year"] == int(year)].copy()

        if matched.empty:
            matched = route_df.sort_values("year").tail(1).copy()
        else:
            matched = matched.sort_values("year").tail(1).copy()
    else:
        matched = route_df.sort_values("year").tail(1).copy()

    return matched.iloc[0].to_dict()


def get_route_history(route: str) -> pd.DataFrame:
    df = load_route_features()

    route_df = df[df["route"] == route].copy()

    if route_df.empty:
        raise ValueError(f"선택한 노선을 찾을 수 없습니다: {route}")

    return route_df.sort_values("year").reset_index(drop=True)


def get_top_risk_routes(year: Optional[int] = None, limit: int = 10) -> pd.DataFrame:
    df = load_route_features()

    if year is not None:
        df = df[df["year"] == int(year)].copy()

    if df.empty:
        return df

    return (
        df.sort_values(["risk_score", "passenger_growth_rate"], ascending=[False, False])
        .head(limit)
        .reset_index(drop=True)
    )


# 기존 app.py 호환용 함수
def load_sample_route_features() -> pd.DataFrame:
    return load_route_features()


def find_route_feature(
    df: pd.DataFrame,
    departure_airport: str = None,
    arrival_airport: str = None,
    departure_date: str = None,
    route: str = None,
    year=None,
) -> dict:
    data = df.copy()

    if route is None:
        if departure_airport is None or arrival_airport is None:
            raise ValueError("route 또는 departure_airport/arrival_airport가 필요합니다.")

        matched = data[
            (data["departure_airport"] == departure_airport)
            & (data["arrival_airport"] == arrival_airport)
        ].copy()
    else:
        matched = data[data["route"] == route].copy()

    if matched.empty:
        available_routes = (
            data[["departure_airport", "arrival_airport", "route"]]
            .drop_duplicates()
            .head(20)
            .to_dict("records")
        )
        raise ValueError(
            f"선택한 노선을 찾을 수 없습니다. "
            f"departure_airport={departure_airport}, arrival_airport={arrival_airport}, route={route}. "
            f"사용 가능한 예시: {available_routes}"
        )

    # departure_date가 들어오면 해당 연도 기준으로 매칭
    if departure_date is not None:
        parsed_date = pd.to_datetime(departure_date, errors="coerce")

        if pd.notna(parsed_date):
            target_year = int(parsed_date.year)
            year_matched = matched[matched["year"] == target_year].copy()

            if not year_matched.empty:
                matched = year_matched

    if year is not None:
        year_matched = matched[matched["year"] == int(year)].copy()

        if not year_matched.empty:
            matched = year_matched

    matched = matched.sort_values("year").tail(1)

    return matched.iloc[0].to_dict()