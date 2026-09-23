import numpy as np
import pandas as pd


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


def select_exchange_column(df):
    candidates = [
        "jpy_krw_change_rate_30d",
        "jpy_krw_change_rate_90d",
        "jpy_krw_change_rate_7d",
        "jpy_krw_change_rate",
    ]

    for column in candidates:
        if column in df.columns:
            return column

    return None


def add_normalized_risk_features(df):
    df = df.copy()

    required_numeric_cols = [
        "passenger_growth_rate",
        "flight_growth_rate",
        "passengers_per_flight",
        "avg_carrier_count",
        "avg_lcc_share",
        "holiday_count",
    ]

    for column in required_numeric_cols:
        if column not in df.columns:
            df[column] = 0.0

        df[column] = clean_numeric(df[column])

    exchange_column = select_exchange_column(df)

    if exchange_column:
        df[exchange_column] = clean_numeric(df[exchange_column])

    # 1. 수요 압력
    # passenger_growth_rate와 passengers_per_flight를 함께 사용
    # 수요-공급 격차는 flight_growth_rate 중복 문제 때문에 사용하지 않음
    df["norm_passenger_growth_pressure"] = percentile_by_year(
        df,
        "passenger_growth_rate",
        higher_is_risk=True,
    )

    df["norm_demand_intensity_pressure"] = percentile_by_year(
        df,
        "passengers_per_flight",
        higher_is_risk=True,
    )

    df["normalized_demand_pressure"] = (
        df["norm_passenger_growth_pressure"] * 0.6
        + df["norm_demand_intensity_pressure"] * 0.4
    )

    # 2. 공급 제약
    # flight_growth_rate가 낮을수록 공급 증가가 부족하다고 판단
    df["normalized_supply_constraint"] = percentile_by_year(
        df,
        "flight_growth_rate",
        higher_is_risk=False,
    )

    # 3. 경쟁도 압력
    # 항공사 수와 LCC 비중이 낮을수록 가격 경쟁 압력이 약하다고 판단
    # 단, 해당 연도 값이 전부 동일하면 중립값 0.5 처리
    df["norm_carrier_pressure"] = percentile_by_year(
        df,
        "avg_carrier_count",
        higher_is_risk=False,
        neutral_if_constant=True,
    )

    df["norm_lcc_pressure"] = percentile_by_year(
        df,
        "avg_lcc_share",
        higher_is_risk=False,
        neutral_if_constant=True,
    )

    df["normalized_competition_pressure"] = (
        df["norm_carrier_pressure"] * 0.6
        + df["norm_lcc_pressure"] * 0.4
    )

    # 4. 환율 압력
    # 현재 데이터는 일본 노선 중심이므로 JPY/KRW 변동률 사용
    # 향후 다국가 확장 시 통화별 컬럼으로 일반화 필요
    if exchange_column:
        df["normalized_exchange_pressure"] = percentile_by_year(
            df,
            exchange_column,
            higher_is_risk=True,
        )
    else:
        df["normalized_exchange_pressure"] = 0.5

    # 5. 정적 공휴일 압력
    # 현재 route_features_japan.csv에서는 holiday_count가 전부 0에 가까우므로
    # 정적 피처에서는 0점 처리하고, 실제 여행일 기준 공휴일 반영은 agents.py에서 별도 처리
    if df["holiday_count"].nunique(dropna=True) <= 1:
        df["normalized_static_holiday_pressure"] = 0.0
    else:
        df["normalized_static_holiday_pressure"] = percentile_by_year(
            df,
            "holiday_count",
            higher_is_risk=True,
            neutral_if_constant=False,
        )

    # 참고용 정규화 기반 기본 점수
    # 실제 최종 점수는 agents.py에서 사용자 여행일 조건까지 반영해 계산 예정
    df["normalized_base_risk_score"] = (
        df["normalized_demand_pressure"] * 35
        + df["normalized_supply_constraint"] * 25
        + df["normalized_competition_pressure"] * 20
        + df["normalized_exchange_pressure"] * 5
        + df["normalized_static_holiday_pressure"] * 15
    ).round(1)

    df["normalized_base_risk_level"] = np.select(
        [
            df["normalized_base_risk_score"] >= 70,
            df["normalized_base_risk_score"] >= 45,
        ],
        [
            "높음",
            "중간",
        ],
        default="낮음",
    )

    return df