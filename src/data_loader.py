from pathlib import Path
from typing import Optional

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "processed" / "route_features_japan.csv"


def _normalize_airport_display(value):
    if pd.isna(value):
        return value

    value = str(value).strip()

    airport_map = {
        "한국": "ICN",
        "인천": "ICN",
        "김포": "GMP",
        "부산": "PUS",
        "김해": "PUS",
        "제주": "CJU",
        "나리타": "NRT",
        "하네다": "HND",
        "간사이": "KIX",
        "오사카": "KIX",
        "후쿠오카": "FUK",
        "삿포로": "CTS",
        "오키나와": "OKA",
        "나고야": "NGO",
        "고베": "UKB",
        "구마모토": "KMJ",
        "구마모도": "KMJ",
        "히로시마": "HIJ",
        "마쓰야마": "MYJ",
        "가고시마": "KOJ",
        "오이타": "OIT",
        "미야자키": "KMI",
        "다카마쓰": "TAK",
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

    if value in airport_map:
        return airport_map[value]

    if "(" in value and ")" in value:
        code = value.split("(")[-1].split(")")[0].strip()
        if len(code) == 3:
            return code

    return value


def _ensure_compatibility_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "year" not in df.columns:
        if "departure_date" in df.columns:
            df["year"] = pd.to_datetime(df["departure_date"], errors="coerce").dt.year
        else:
            raise ValueError(
                "데이터에 year 컬럼이 없습니다. "
                "data/processed/route_features_japan.csv 파일을 확인해야 합니다."
            )

    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    if "departure_airport" not in df.columns:
        if "origin" in df.columns:
            df["departure_airport"] = df["origin"]
        else:
            df["departure_airport"] = "ICN"

    if "arrival_airport" not in df.columns:
        if "destination" in df.columns:
            df["arrival_airport"] = df["destination"]
        else:
            df["arrival_airport"] = ""

    df["departure_airport"] = df["departure_airport"].apply(_normalize_airport_display)
    df["arrival_airport"] = df["arrival_airport"].apply(_normalize_airport_display)

    if "departure_date" not in df.columns:
        df["departure_date"] = df["year"].astype(str) + "-01-01"

    if "route_name" not in df.columns:
        df["route_name"] = (
            df["departure_airport"].astype(str)
            + "-"
            + df["arrival_airport"].astype(str)
        )

    if "route" not in df.columns:
        df["route"] = df["route_name"]

    default_numeric_columns = {
        "passenger_growth_rate": 0,
        "flight_growth_rate": 0,
        "cargo_growth_rate": 0,
        "passengers_per_flight": 0,
        "avg_carrier_count": 0,
        "avg_lcc_share": 0,
        "jpy_krw_rate": 0,
        "jpy_krw_change_rate": 0,
        "jpy_krw_change_rate_30d": 0,
        "holiday_count": 0,
        "days_to_holiday": 0,
        "delay_rate": 0,
        "cancel_count": 0,
        "risk_score": 0,
    }

    for col, default_value in default_numeric_columns.items():
        if col not in df.columns:
            df[col] = default_value

        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default_value)

    if "jpy_krw_change_rate" in df.columns and "jpy_krw_change_rate_30d" in df.columns:
        df["jpy_krw_change_rate"] = df["jpy_krw_change_rate_30d"].fillna(
            df["jpy_krw_change_rate"]
        )

    if "holiday_name" not in df.columns:
        if "holiday_names" in df.columns:
            df["holiday_name"] = df["holiday_names"].fillna("")
        else:
            df["holiday_name"] = ""

    if "risk_level" not in df.columns:
        df["risk_level"] = df["risk_score"].apply(_classify_risk_level)

    if "purchase_timing_recommendation" not in df.columns:
        df["purchase_timing_recommendation"] = df["risk_level"].apply(
            _recommend_purchase_timing
        )

    if "recommendation" not in df.columns:
        df["recommendation"] = df["purchase_timing_recommendation"]

    return df


def _classify_risk_level(score):
    try:
        score = float(score)
    except Exception:
        score = 0

    if score >= 70:
        return "높음"
    if score >= 45:
        return "중간"
    return "낮음"


def _recommend_purchase_timing(risk_level):
    if risk_level == "높음":
        return "빠른 구매 검토"
    if risk_level == "중간":
        return "가격 모니터링 후 구매"
    return "대기 가능"


def load_sample_route_features() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"최종 피처 파일을 찾을 수 없습니다: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    df = _ensure_compatibility_columns(df)

    return df


def find_route_feature(
    df: pd.DataFrame,
    departure_airport: str,
    arrival_airport: str,
    departure_date: Optional[str] = None,
    year: Optional[int] = None,
):
    df = _ensure_compatibility_columns(df)

    departure_airport = _normalize_airport_display(departure_airport)
    arrival_airport = _normalize_airport_display(arrival_airport)

    matched = df[
        (df["departure_airport"].astype(str) == str(departure_airport))
        & (df["arrival_airport"].astype(str) == str(arrival_airport))
    ].copy()

    if matched.empty:
        raise ValueError(
            f"선택한 노선 데이터를 찾을 수 없습니다: {departure_airport} → {arrival_airport}"
        )

    if year is None and departure_date is not None:
        year = pd.to_datetime(departure_date).year

    if year is not None:
        year = int(year)

        exact_year = matched[matched["year"].astype(int) == year]

        if not exact_year.empty:
            matched = exact_year
        else:
            past_years = matched[matched["year"].astype(int) <= year]

            if not past_years.empty:
                latest_year = past_years["year"].max()
                matched = past_years[past_years["year"] == latest_year]
            else:
                latest_year = matched["year"].max()
                matched = matched[matched["year"] == latest_year]

    matched = matched.sort_values("year", ascending=False)

    return matched.iloc[0].to_dict()


def get_top_risk_routes(year: Optional[int] = None, limit: int = 10) -> pd.DataFrame:
    df = load_sample_route_features()

    if year is not None:
        year_df = df[df["year"].astype(int) == int(year)]

        if not year_df.empty:
            df = year_df

    return (
        df.sort_values("risk_score", ascending=False)
        .drop_duplicates(subset=["departure_airport", "arrival_airport"])
        .head(limit)
        .copy()
    )