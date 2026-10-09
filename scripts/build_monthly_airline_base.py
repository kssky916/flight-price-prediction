from pathlib import Path
import re
import warnings

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

PASSENGER_DIR = (
    ROOT_DIR
    / "data/raw/monthly_airline_stats/passenger"
)

FLIGHT_DIR = (
    ROOT_DIR
    / "data/raw/monthly_airline_stats/flight"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/airline_monthly_base.csv"
)


warnings.filterwarnings(
    "ignore",
    message="Workbook contains no default style"
)


def normalize_year_month(value):
    if pd.isna(value):
        return None

    text = str(value).strip()

    match = re.search(
        r"(\d{4})\D*(\d{1,2})",
        text,
    )

    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2))

    if not 1 <= month <= 12:
        return None

    return f"{year:04d}-{month:02d}"


def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace(" ", "", regex=False),
        errors="coerce",
    )


def load_folder(folder, value_column):
    files = sorted(folder.glob("*.xlsx"))

    if not files:
        raise FileNotFoundError(
            f"파일이 없습니다: {folder}"
        )

    frames = []

    for file in files:
        print(f"[LOAD] {file.name}")

        df = pd.read_excel(
            file,
            sheet_name="Data",
        )

        df = df.dropna(how="all")

        required = [
            "항공사명",
            "년월",
            value_column,
        ]

        missing = [
            col
            for col in required
            if col not in df.columns
        ]

        if missing:
            raise KeyError(
                f"{file.name} 컬럼 누락: {missing}"
            )

        # 전체 합계 제거
        df = df[
            ~df["항공사명"]
            .astype(str)
            .str.contains("합계", na=False)
        ].copy()

        result = pd.DataFrame()

        result["year_month"] = (
            df["년월"]
            .apply(normalize_year_month)
        )

        result["airline"] = (
            df["항공사명"]
            .astype(str)
            .str.strip()
        )

        result[value_column] = (
            clean_numeric(df[value_column])
        )

        result = result.dropna(
            subset=[
                "year_month",
                "airline",
                value_column,
            ]
        )

        frames.append(result)

    return pd.concat(
        frames,
        ignore_index=True,
    )


def main():
    print("\n=== 항공사 여객 데이터 ===")

    passenger = load_folder(
        PASSENGER_DIR,
        "여객(명)",
    )

    passenger = passenger.rename(
        columns={
            "여객(명)": "passenger_count"
        }
    )

    print("\n=== 항공사 운항 데이터 ===")

    flight = load_folder(
        FLIGHT_DIR,
        "운항(편)",
    )

    flight = flight.rename(
        columns={
            "운항(편)": "flight_count"
        }
    )

    # 혹시 동일 항공사/월이 중복이면 합산
    passenger = (
        passenger.groupby(
            ["year_month", "airline"],
            as_index=False,
        )["passenger_count"]
        .sum()
    )

    flight = (
        flight.groupby(
            ["year_month", "airline"],
            as_index=False,
        )["flight_count"]
        .sum()
    )

    merged = passenger.merge(
        flight,
        on=[
            "year_month",
            "airline",
        ],
        how="outer",
        validate="one_to_one",
    )

    merged["passengers_per_flight"] = (
        merged["passenger_count"]
        / merged["flight_count"].replace(
            0,
            pd.NA,
        )
    )

    merged = merged.sort_values(
        ["airline", "year_month"]
    ).reset_index(drop=True)

    print("\n=== 결과 ===")
    print("총 행 수:", len(merged))
    print(
        "항공사 수:",
        merged["airline"].nunique()
    )
    print(
        "기간:",
        merged["year_month"].min(),
        "~",
        merged["year_month"].max(),
    )

    print("\n결측치:")
    print(merged.isna().sum())

    print("\n항공사 목록:")
    print(
        sorted(
            merged["airline"]
            .dropna()
            .unique()
            .tolist()
        )
    )

    print("\n샘플:")
    print(
        merged.head(30)
        .to_string(index=False)
    )

    merged.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\n[SAVED] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()