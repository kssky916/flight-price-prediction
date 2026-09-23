from pathlib import Path

import numpy as np
import pandas as pd


DATA_PATH = Path("data/processed/route_features_japan.csv")


def clean_numeric(series):
    series = pd.to_numeric(series, errors="coerce")
    series = series.replace([np.inf, -np.inf], np.nan)

    if series.notna().sum() == 0:
        return pd.Series([0.0] * len(series), index=series.index)

    median_value = series.median()
    return series.fillna(median_value)


def percentile_by_year(df, column, higher_is_risk=True, neutral_if_constant=True):
    result = pd.Series(index=df.index, dtype=float)

    for year, group in df.groupby("year"):
        values = clean_numeric(group[column])

        if values.nunique(dropna=True) <= 1:
            fill_value = 0.5 if neutral_if_constant else 0.0
            result.loc[group.index] = fill_value
            continue

        percentile = values.rank(pct=True, method="average")

        if higher_is_risk:
            result.loc[group.index] = percentile
        else:
            result.loc[group.index] = 1 - percentile

    return result.fillna(0.5)


def main():
    df = pd.read_csv(DATA_PATH)

    df["passenger_growth_rate"] = clean_numeric(df["passenger_growth_rate"])
    df["flight_growth_rate"] = clean_numeric(df["flight_growth_rate"])
    df["passengers_per_flight"] = clean_numeric(df["passengers_per_flight"])
    df["avg_carrier_count"] = clean_numeric(df["avg_carrier_count"])
    df["avg_lcc_share"] = clean_numeric(df["avg_lcc_share"])
    df["holiday_count"] = clean_numeric(df["holiday_count"])

    if "jpy_krw_change_rate_30d" in df.columns:
        exchange_col = "jpy_krw_change_rate_30d"
    elif "jpy_krw_change_rate_90d" in df.columns:
        exchange_col = "jpy_krw_change_rate_90d"
    elif "jpy_krw_change_rate_7d" in df.columns:
        exchange_col = "jpy_krw_change_rate_7d"
    else:
        exchange_col = None

    df["demand_supply_gap"] = df["passenger_growth_rate"] - df["flight_growth_rate"]

    df["norm_demand_supply_gap"] = percentile_by_year(
        df,
        "demand_supply_gap",
        higher_is_risk=True,
    )

    df["norm_supply_pressure"] = percentile_by_year(
        df,
        "flight_growth_rate",
        higher_is_risk=False,
    )

    df["norm_demand_intensity"] = percentile_by_year(
        df,
        "passengers_per_flight",
        higher_is_risk=True,
    )

    df["norm_carrier_pressure"] = percentile_by_year(
        df,
        "avg_carrier_count",
        higher_is_risk=False,
    )

    df["norm_lcc_pressure"] = percentile_by_year(
        df,
        "avg_lcc_share",
        higher_is_risk=False,
    )

    df["norm_competition_pressure"] = (
        df["norm_carrier_pressure"] * 0.6
        + df["norm_lcc_pressure"] * 0.4
    )

    if exchange_col:
        df[exchange_col] = clean_numeric(df[exchange_col])
        df["norm_exchange_pressure"] = percentile_by_year(
            df,
            exchange_col,
            higher_is_risk=True,
        )
    else:
        df["norm_exchange_pressure"] = 0.5

    if df["holiday_count"].nunique(dropna=True) <= 1:
        df["norm_holiday_pressure"] = 0.0
    else:
        df["norm_holiday_pressure"] = percentile_by_year(
            df,
            "holiday_count",
            higher_is_risk=True,
            neutral_if_constant=False,
        )

    df["normalized_risk_score"] = (
        df["norm_demand_supply_gap"] * 35
        + df["norm_supply_pressure"] * 20
        + df["norm_demand_intensity"] * 15
        + df["norm_competition_pressure"] * 20
        + df["norm_exchange_pressure"] * 5
        + df["norm_holiday_pressure"] * 5
    ).round(1)

    df["normalized_risk_level"] = np.select(
        [
            df["normalized_risk_score"] >= 70,
            df["normalized_risk_score"] >= 45,
        ],
        [
            "높음",
            "중간",
        ],
        default="낮음",
    )

    print("\n[정규화 위험도 점수 분포]")
    print(df["normalized_risk_score"].describe())

    print("\n[기존 위험도 점수 분포]")
    if "risk_score" in df.columns:
        print(df["risk_score"].describe())

    print("\n[정규화 위험도 상위 20개]")
    display_cols = [
        "year",
        "route",
        "passenger_growth_rate",
        "flight_growth_rate",
        "demand_supply_gap",
        "passengers_per_flight",
        "avg_carrier_count",
        "avg_lcc_share",
        "risk_score",
        "risk_level",
        "normalized_risk_score",
        "normalized_risk_level",
    ]
    display_cols = [col for col in display_cols if col in df.columns]

    print(
        df.sort_values("normalized_risk_score", ascending=False)[display_cols]
        .head(20)
        .to_string(index=False)
    )

    print("\n[기존 risk_score 상위 20개]")
    print(
        df.sort_values("risk_score", ascending=False)[display_cols]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()