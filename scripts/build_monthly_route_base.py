from pathlib import Path
import re
import warnings

import pandas as pd


# =========================================================
# 경로 설정
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

PASSENGER_DIR = ROOT_DIR / "data/raw/monthly_route_stats/passenger"
FLIGHT_DIR = ROOT_DIR / "data/raw/monthly_route_stats/flight"

OUTPUT_DIR = ROOT_DIR / "data/processed/ml"
OUTPUT_PATH = OUTPUT_DIR / "route_monthly_base.csv"


# Excel 기본 스타일 관련 경고 숨김
warnings.filterwarnings(
    "ignore",
    message="Workbook contains no default style"
)


# =========================================================
# 공통 함수
# =========================================================

def load_excel_folder(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.xlsx"))

    if not files:
        raise FileNotFoundError(
            f"Excel 파일을 찾을 수 없습니다: {folder}"
        )

    frames = []

    for file in files:
        print(f"[LOAD] {file.name}")

        df = pd.read_excel(
            file,
            sheet_name="Data"
        )

        df = df.dropna(how="all")
        df = df.dropna(axis=1, how="all")

        df.columns = [
            str(col).strip().replace("\n", " ")
            for col in df.columns
        ]

        df["source_file"] = file.name

        frames.append(df)

    return pd.concat(
        frames,
        ignore_index=True
    )


def normalize_year_month(value):
    """
    예:
    2020년 01월 -> 2020-01
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    match = re.search(
        r"(\d{4})\D*(\d{1,2})",
        text
    )

    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2))

    if not 1 <= month <= 12:
        return None

    return f"{year:04d}-{month:02d}"


def extract_airport_code(value):
    """
    예:
    인천(ICN) -> ICN
    나리타(NRT) -> NRT
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    match = re.search(
        r"\(([A-Z]{3})\)",
        text
    )

    if match:
        return match.group(1)

    if re.fullmatch(r"[A-Z]{3}", text):
        return text

    return None


def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False),
        errors="coerce"
    )


def remove_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 합계 / 기타 합계 행 제거
    """

    df = df.copy()

    route1 = df["노선1"].astype(str)
    route2 = df["노선2"].astype(str)

    total_mask = (
        route1.str.contains("합계", na=False)
        | route2.str.contains("합계", na=False)
    )

    return df.loc[~total_mask].copy()


# =========================================================
# 여객 데이터 정제
# =========================================================

def prepare_passenger_data(
    df: pd.DataFrame
) -> pd.DataFrame:

    required_columns = [
        "노선1",
        "노선2",
        "년월",
        "여객(명)",
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise KeyError(
            f"여객 데이터 필수 컬럼 누락: {missing}"
        )

    df = remove_total_rows(df)

    result = pd.DataFrame()

    result["year_month"] = (
        df["년월"]
        .apply(normalize_year_month)
    )

    result["origin"] = (
        df["노선1"]
        .apply(extract_airport_code)
    )

    result["destination"] = (
        df["노선2"]
        .apply(extract_airport_code)
    )

    result["passenger_count"] = (
        clean_numeric(df["여객(명)"])
    )

    result = result.dropna(
        subset=[
            "year_month",
            "origin",
            "destination",
            "passenger_count",
        ]
    )

    return result


# =========================================================
# 운항 데이터 정제
# =========================================================

def prepare_flight_data(
    df: pd.DataFrame
) -> pd.DataFrame:

    required_columns = [
        "노선1",
        "노선2",
        "년월",
        "운항(편)",
    ]

    missing = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise KeyError(
            f"운항 데이터 필수 컬럼 누락: {missing}"
        )

    df = remove_total_rows(df)

    result = pd.DataFrame()

    result["year_month"] = (
        df["년월"]
        .apply(normalize_year_month)
    )

    result["origin"] = (
        df["노선1"]
        .apply(extract_airport_code)
    )

    result["destination"] = (
        df["노선2"]
        .apply(extract_airport_code)
    )

    result["flight_count"] = (
        clean_numeric(df["운항(편)"])
    )

    result = result.dropna(
        subset=[
            "year_month",
            "origin",
            "destination",
            "flight_count",
        ]
    )

    return result


# =========================================================
# 월별 노선 단위 집계
# =========================================================

def aggregate_monthly(
    df: pd.DataFrame,
    value_column: str
) -> pd.DataFrame:

    return (
        df.groupby(
            [
                "year_month",
                "origin",
                "destination",
            ],
            as_index=False
        )[value_column]
        .sum()
    )


# =========================================================
# 품질 검증
# =========================================================

def validate_result(df: pd.DataFrame):
    print("\n" + "=" * 70)
    print("데이터 품질 확인")
    print("=" * 70)

    print(f"총 행 수: {len(df):,}")
    print(f"노선 수: {df['route'].nunique():,}")

    print(
        "기간:",
        df["year_month"].min(),
        "~",
        df["year_month"].max(),
    )

    print("\n연도별 행 수:")
    print(
        df.assign(
            year=df["year_month"].str[:4]
        )
        .groupby("year")
        .size()
    )

    print("\n결측치:")
    print(df.isna().sum())

    print("\n운항편수 0 이하:")
    print(
        (df["flight_count"] <= 0).sum()
    )

    print("\n여객수 음수:")
    print(
        (df["passenger_count"] < 0).sum()
    )

    duplicate_count = df.duplicated(
        subset=[
            "year_month",
            "origin",
            "destination",
        ]
    ).sum()

    print("\n월별 노선 중복:")
    print(duplicate_count)

    print("\n샘플:")
    print(
        df.head(20)
        .to_string(index=False)
    )


# =========================================================
# 실행
# =========================================================

def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\n=== 1. 노선시계열 여객 데이터 로드 ===")
    passenger_raw = load_excel_folder(
        PASSENGER_DIR
    )

    print(
        f"여객 원본 행 수: "
        f"{len(passenger_raw):,}"
    )

    print("\n=== 2. 노선시계열 운항 데이터 로드 ===")
    flight_raw = load_excel_folder(
        FLIGHT_DIR
    )

    print(
        f"운항 원본 행 수: "
        f"{len(flight_raw):,}"
    )

    print("\n=== 3. 데이터 정제 ===")

    passenger = prepare_passenger_data(
        passenger_raw
    )

    flight = prepare_flight_data(
        flight_raw
    )

    print(
        f"정제 후 여객 행 수: "
        f"{len(passenger):,}"
    )

    print(
        f"정제 후 운항 행 수: "
        f"{len(flight):,}"
    )

    print("\n=== 4. 월별 노선 단위 집계 ===")

    passenger_monthly = aggregate_monthly(
        passenger,
        "passenger_count"
    )

    flight_monthly = aggregate_monthly(
        flight,
        "flight_count"
    )

    print(
        f"여객 월별 노선 행 수: "
        f"{len(passenger_monthly):,}"
    )

    print(
        f"운항 월별 노선 행 수: "
        f"{len(flight_monthly):,}"
    )

    print("\n=== 5. 여객 + 운항 병합 ===")

    merged = passenger_monthly.merge(
        flight_monthly,
        on=[
            "year_month",
            "origin",
            "destination",
        ],
        how="outer",
        validate="one_to_one"
    )

    merged["route"] = (
        merged["origin"]
        + "-"
        + merged["destination"]
    )

    merged["passengers_per_flight"] = (
        merged["passenger_count"]
        / merged["flight_count"].replace(
            0,
            pd.NA
        )
    )

    # 코로나 영향 구간을 삭제하지 않고 별도 Feature로 표시
    merged["covid_period"] = (
        merged["year_month"]
        .str[:4]
        .isin(["2020", "2021"])
        .astype(int)
    )

    merged = merged[
        [
            "year_month",
            "origin",
            "destination",
            "route",
            "passenger_count",
            "flight_count",
            "passengers_per_flight",
            "covid_period",
        ]
    ]

    merged = merged.sort_values(
        [
            "route",
            "year_month",
        ]
    ).reset_index(drop=True)

    print("\n=== 6. 품질 검증 ===")

    validate_result(merged)

    print("\n=== 7. CSV 저장 ===")

    merged.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"\n[SAVED] {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()