import pandas as pd
from pathlib import Path


DATA_PATH = Path("data/processed/route_features_japan.csv")


def main():
    df = pd.read_csv(DATA_PATH)

    print("\n[컬럼 목록]")
    print(df.columns.tolist())

    target_cols = [
        "year",
        "departure_airport",
        "arrival_airport",
        "route",
        "passenger_growth_rate",
        "flight_growth_rate",
        "passengers_per_flight",
        "avg_carrier_count",
        "avg_lcc_share",
        "jpy_krw_change_rate",
        "holiday_count",
        "risk_score",
        "risk_level",
        "purchase_timing_recommendation",
    ]

    existing_cols = [col for col in target_cols if col in df.columns]

    print("\n[주요 컬럼 샘플]")
    print(df[existing_cols].head(10))

    numeric_cols = [
        "passenger_growth_rate",
        "flight_growth_rate",
        "passengers_per_flight",
        "avg_carrier_count",
        "avg_lcc_share",
        "jpy_krw_change_rate",
        "holiday_count",
        "risk_score",
    ]

    numeric_cols = [col for col in numeric_cols if col in df.columns]

    print("\n[전체 수치형 피처 분포]")
    print(df[numeric_cols].describe())

    if "year" in df.columns:
        print("\n[연도별 수치형 피처 분포]")
        for year, group in df.groupby("year"):
            print(f"\n===== {year} =====")
            print(group[numeric_cols].describe())

    if "risk_score" in df.columns:
        print("\n[위험도 상위 20개 노선]")
        display_cols = [
            "year",
            "departure_airport",
            "arrival_airport",
            "route",
            "passenger_growth_rate",
            "flight_growth_rate",
            "avg_carrier_count",
            "avg_lcc_share",
            "risk_score",
            "risk_level",
        ]
        display_cols = [col for col in display_cols if col in df.columns]

        print(
            df.sort_values("risk_score", ascending=False)[display_cols]
            .head(20)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()