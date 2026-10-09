from pathlib import Path
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

ROUTE_PATH = (
    ROOT_DIR
    / "data/processed/ml/route_monthly_japan.csv"
)

MARKET_PATH = (
    ROOT_DIR
    / "data/processed/ml/airline_market_monthly.csv"
)

EXCHANGE_PATH = (
    ROOT_DIR
    / "data/processed/ml/exchange_rate_monthly.csv"
)

KR_HOLIDAY_PATH = (
    ROOT_DIR
    / "data/processed/processed_holidays_clean.csv"
)

JP_HOLIDAY_PATH = (
    ROOT_DIR
    / "data/processed/japan_holidays_clean.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_feature_base.csv"
)


def build_holiday_monthly(path, prefix):
    df = pd.read_csv(path)

    df["holiday_date"] = pd.to_datetime(
        df["holiday_date"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["holiday_date"]
    ).copy()

    df["year_month"] = (
        df["holiday_date"]
        .dt.to_period("M")
        .astype(str)
    )

    monthly = (
        df.groupby(
            "year_month",
            as_index=False
        )
        .agg(
            holiday_count=(
                "holiday_date",
                "nunique"
            ),
            holiday_name_count=(
                "holiday_name",
                "nunique"
            ),
        )
    )

    monthly = monthly.rename(
        columns={
            "holiday_count":
                f"{prefix}_holiday_count",
            "holiday_name_count":
                f"{prefix}_holiday_name_count",
        }
    )

    monthly[f"{prefix}_has_holiday"] = (
        monthly[
            f"{prefix}_holiday_count"
        ] > 0
    ).astype(int)

    return monthly


def main():

    print("=== 1. 데이터 로드 ===")

    route = pd.read_csv(ROUTE_PATH)
    market = pd.read_csv(MARKET_PATH)
    exchange = pd.read_csv(EXCHANGE_PATH)

    kr_holiday = build_holiday_monthly(
        KR_HOLIDAY_PATH,
        "kr"
    )

    jp_holiday = build_holiday_monthly(
        JP_HOLIDAY_PATH,
        "jp"
    )

    print("일본 노선:", len(route))
    print("항공시장 월:", len(market))
    print("환율 월:", len(exchange))
    print("한국 공휴일 월:", len(kr_holiday))
    print("일본 공휴일 월:", len(jp_holiday))

    # ---------------------------------------------
    # 2. 노선 + 시장
    # ---------------------------------------------

    df = route.merge(
        market,
        on="year_month",
        how="left",
        validate="many_to_one"
    )

    # ---------------------------------------------
    # 3. 환율
    # ---------------------------------------------

    df = df.merge(
        exchange,
        on="year_month",
        how="left",
        validate="many_to_one"
    )

    # ---------------------------------------------
    # 4. 한국 공휴일
    # ---------------------------------------------

    df = df.merge(
        kr_holiday,
        on="year_month",
        how="left",
        validate="many_to_one"
    )

    # ---------------------------------------------
    # 5. 일본 공휴일
    # ---------------------------------------------

    df = df.merge(
        jp_holiday,
        on="year_month",
        how="left",
        validate="many_to_one"
    )

    # 공휴일이 없는 월은 0
    holiday_columns = [
        "kr_holiday_count",
        "kr_holiday_name_count",
        "kr_has_holiday",
        "jp_holiday_count",
        "jp_holiday_name_count",
        "jp_has_holiday",
    ]

    df[holiday_columns] = (
        df[holiday_columns]
        .fillna(0)
        .astype(int)
    )

    # ---------------------------------------------
    # 6. 날짜 Feature
    # ---------------------------------------------

    dt = pd.to_datetime(
        df["year_month"],
        format="%Y-%m"
    )

    df["year"] = dt.dt.year
    df["month"] = dt.dt.month

    # 월의 계절성을 숫자로 표현
    df["month_sin"] = np.sin(
        2 * np.pi * df["month"] / 12
    )

    df["month_cos"] = np.cos(
        2 * np.pi * df["month"] / 12
    )

    # 코로나 기간 표시
    df["covid_period"] = (
        df["year"]
        .isin([2020, 2021])
        .astype(int)
    )

    # ---------------------------------------------
    # 7. 정렬
    # ---------------------------------------------

    df = df.sort_values(
        [
            "route",
            "year_month"
        ]
    ).reset_index(drop=True)

    # ---------------------------------------------
    # 8. 검증
    # ---------------------------------------------

    print("\n=== ML Feature Base 검증 ===")

    print("총 행 수:", len(df))
    print(
        "노선 수:",
        df["route"].nunique()
    )

    print(
        "기간:",
        df["year_month"].min(),
        "~",
        df["year_month"].max()
    )

    duplicate_count = df.duplicated(
        [
            "route",
            "year_month"
        ]
    ).sum()

    print(
        "노선-월 중복:",
        duplicate_count
    )

    print("\n주요 결측치:")

    check_columns = [
        "passenger_count",
        "flight_count",
        "market_passenger_total",
        "market_passenger_flights",
        "jpy_krw_avg",
        "jpy_krw_mom_pct",
        "jpy_krw_3m_pct",
        "kr_holiday_count",
        "jp_holiday_count",
    ]

    print(
        df[check_columns]
        .isna()
        .sum()
    )

    print("\n컬럼:")
    print(df.columns.tolist())

    print("\n샘플:")
    print(
        df.head(20)
        .to_string(index=False)
    )

    # ---------------------------------------------
    # 9. 저장
    # ---------------------------------------------

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"\n[SAVED] {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()