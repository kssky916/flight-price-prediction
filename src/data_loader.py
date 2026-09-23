from pathlib import Path
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd

from src.risk_normalizer import add_normalized_risk_features


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "processed" / "route_features_japan.csv"


AIRPORT_NAME_TO_CODE = {
    "한국": "ICN",
    "인천": "ICN",
    "서울": "ICN",
    "김포": "GMP",
    "부산": "PUS",
    "김해": "PUS",
    "제주": "CJU",
    "도쿄": "NRT",
    "나리타": "NRT",
    "하네다": "HND",
    "오사카": "KIX",
    "간사이": "KIX",
    "후쿠오카": "FUK",
    "삿포로": "CTS",
    "치토세": "CTS",
    "오키나와": "OKA",
    "오끼나와": "OKA",
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


def _to_python_value(value):
    if value is None:
        return None

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)

    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None
        return value

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if pd.isna(value):
        return None

    return value


def _row_to_dict(row: pd.Series) -> Dict[str, Any]:
    return {key: _to_python_value(value) for key, value in row.to_dict().items()}


def normalize_airport_code(value) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if "(" in value and ")" in value:
        code = value.split("(")[-1].split(")")[0].strip()

        if code:
            return code.upper()

    upper_value = value.upper()

    if len(upper_value) == 3 and upper_value.isalpha():
        return upper_value

    return AIRPORT_NAME_TO_CODE.get(value, value)


def _select_exchange_column(df: pd.DataFrame) -> Optional[str]:
    candidates = [
        "jpy_krw_change_rate",
        "jpy_krw_change_rate_30d",
        "jpy_krw_change_rate_90d",
        "jpy_krw_change_rate_7d",
    ]

    for column in candidates:
        if column in df.columns:
            return column

    return None


def _ensure_basic_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "departure_airport" not in df.columns:
        if "origin" in df.columns:
            df["departure_airport"] = df["origin"].apply(normalize_airport_code)
        else:
            df["departure_airport"] = ""

    if "arrival_airport" not in df.columns:
        if "destination" in df.columns:
            df["arrival_airport"] = df["destination"].apply(normalize_airport_code)
        else:
            df["arrival_airport"] = ""

    if "route" not in df.columns:
        df["route"] = (
            df["departure_airport"].astype(str)
            + "-"
            + df["arrival_airport"].astype(str)
        )

    if "route_name" not in df.columns:
        df["route_name"] = df["route"]

    if "year" not in df.columns:
        df["year"] = pd.Timestamp.today().year

    df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(0).astype(int)

    if "departure_date" not in df.columns:
        df["departure_date"] = df["year"].astype(str) + "-01-01"

    exchange_column = _select_exchange_column(df)

    if "jpy_krw_change_rate" not in df.columns:
        if exchange_column:
            df["jpy_krw_change_rate"] = df[exchange_column]
        else:
            df["jpy_krw_change_rate"] = 0.0

    default_numeric_columns = {
        "passenger_growth_rate": 0.0,
        "flight_growth_rate": 0.0,
        "passengers_per_flight": 0.0,
        "avg_carrier_count": 0.0,
        "avg_lcc_share": 0.0,
        "holiday_count": 0.0,
        "delay_rate": 0.0,
        "cancel_count": 0.0,
        "jpy_krw_rate": 0.0,
        "jpy_krw_change_rate": 0.0,
    }

    for column, default_value in default_numeric_columns.items():
        if column not in df.columns:
            df[column] = default_value

        df[column] = pd.to_numeric(df[column], errors="coerce")
        df[column] = df[column].replace([np.inf, -np.inf], np.nan)
        df[column] = df[column].fillna(default_value)

    if "holiday_name" not in df.columns:
        if "holiday_names" in df.columns:
            df["holiday_name"] = df["holiday_names"].fillna("").astype(str)
        else:
            df["holiday_name"] = ""

    if "risk_score" not in df.columns:
        df["risk_score"] = 0.0

    if "risk_level" not in df.columns:
        df["risk_level"] = ""

    if "purchase_timing_recommendation" not in df.columns:
        df["purchase_timing_recommendation"] = ""

    return df


def load_sample_route_features(data_path: Optional[str] = None) -> pd.DataFrame:
    path = Path(data_path) if data_path else DEFAULT_DATA_PATH

    if not path.exists():
        raise FileNotFoundError(f"정제 데이터 파일을 찾을 수 없습니다: {path}")

    df = pd.read_csv(path, encoding="utf-8-sig")
    df = _ensure_basic_columns(df)

    # 정규화 기반 위험도 피처 추가
    df = add_normalized_risk_features(df)

    return df


def _select_target_year(
    available_years: List[int],
    departure_date: Optional[str] = None,
    year: Optional[int] = None,
) -> int:
    available_years = sorted([int(value) for value in available_years])

    if not available_years:
        raise ValueError("분석 가능한 연도 데이터가 없습니다.")

    if year is not None:
        target_year = int(year)
    elif departure_date:
        target_year = int(str(departure_date)[:4])
    else:
        target_year = max(available_years)

    if target_year in available_years:
        return target_year

    past_years = [available_year for available_year in available_years if available_year <= target_year]

    if past_years:
        return max(past_years)

    return max(available_years)


def find_route_feature(
    df: pd.DataFrame,
    departure_airport: str,
    arrival_airport: str,
    departure_date: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    departure_code = normalize_airport_code(departure_airport)
    arrival_code = normalize_airport_code(arrival_airport)

    if "departure_airport" not in df.columns or "arrival_airport" not in df.columns:
        df = _ensure_basic_columns(df)

    route_df = df[
        (df["departure_airport"] == departure_code)
        & (df["arrival_airport"] == arrival_code)
    ].copy()

    if route_df.empty:
        available_routes = (
            df[["departure_airport", "arrival_airport"]]
            .drop_duplicates()
            .head(20)
            .to_dict("records")
        )

        raise ValueError(
            f"해당 노선 데이터를 찾을 수 없습니다: {departure_code} → {arrival_code} / "
            f"확인 가능한 노선 예시: {available_routes}"
        )

    target_year = _select_target_year(
        available_years=route_df["year"].dropna().astype(int).unique().tolist(),
        departure_date=departure_date,
        year=year,
    )

    selected_df = route_df[route_df["year"].astype(int) == target_year].copy()

    if selected_df.empty:
        selected_df = route_df.sort_values("year", ascending=False).head(1)

    else:
        selected_df = selected_df.sort_values("year", ascending=False).head(1)

    row = selected_df.iloc[0]
    result = _row_to_dict(row)

    result["departure_airport"] = departure_code
    result["arrival_airport"] = arrival_code

    if departure_date:
        result["departure_date"] = str(departure_date)

    return result


def get_top_risk_routes(
    df: pd.DataFrame,
    departure_airport: Optional[str] = None,
    limit: int = 5,
    use_normalized_score: bool = True,
) -> pd.DataFrame:
    if df.empty:
        return df

    result_df = df.copy()

    if departure_airport:
        departure_code = normalize_airport_code(departure_airport)
        result_df = result_df[result_df["departure_airport"] == departure_code].copy()

    if result_df.empty:
        return result_df

    if use_normalized_score and "normalized_base_risk_score" in result_df.columns:
        sort_column = "normalized_base_risk_score"
    elif "risk_score" in result_df.columns:
        sort_column = "risk_score"
    else:
        return result_df.head(limit)

    return (
        result_df
        .sort_values(sort_column, ascending=False)
        .drop_duplicates(subset=["departure_airport", "arrival_airport"])
        .head(limit)
        .copy()
    )