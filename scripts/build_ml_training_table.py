from pathlib import Path
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

BASE_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_feature_base.csv"
)

COVERAGE_PATH = (
    ROOT_DIR
    / "data/processed/ml/japan_route_coverage.csv"
)

KR_HOLIDAY_PATH = (
    ROOT_DIR
    / "data/processed/processed_holidays_clean.csv"
)

JP_HOLIDAY_PATH = (
    ROOT_DIR
    / "data/processed/japan_holidays_clean.csv"
)

ALL_OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_feature_engineered.csv"
)

TRAIN_OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_training_table.csv"
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

    df["target_month"] = (
        df["holiday_date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    monthly = (
        df.groupby(
            "target_month",
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
                f"next_{prefix}_holiday_count",
            "holiday_name_count":
                f"next_{prefix}_holiday_name_count",
        }
    )

    monthly[f"next_{prefix}_has_holiday"] = (
        monthly[
            f"next_{prefix}_holiday_count"
        ] > 0
    ).astype(int)

    return monthly


def get_candidate_routes(coverage):
    candidate = coverage[
        "ml_candidate"
    ]

    if candidate.dtype == bool:
        mask = candidate
    else:
        mask = (
            candidate.astype(str)
            .str.lower()
            .eq("true")
        )

    return (
        coverage.loc[mask, "route"]
        .dropna()
        .unique()
        .tolist()
    )


def engineer_route(group):
    group = (
        group
        .sort_values("date")
        .copy()
    )

    route = group["route"].iloc[0]

    full_index = pd.date_range(
        group["date"].min(),
        group["date"].max(),
        freq="MS"
    )

    panel = (
        group.set_index("date")
        .reindex(full_index)
    )

    panel.index.name = "date"

    # 실제 원본에 존재한 월인지 표시
    panel["row_observed"] = (
        panel["year_month"]
        .notna()
        .astype(int)
    )

    panel["route"] = route

    # -----------------------------------------
    # 현재 월 기준 과거 여객 Feature
    # -----------------------------------------

    panel["current_passenger_count"] = (
        panel["passenger_count"]
    )

    panel["passenger_prev_1m"] = (
        panel["passenger_count"]
        .shift(1)
    )

    panel["passenger_prev_2m"] = (
        panel["passenger_count"]
        .shift(2)
    )

    panel["passenger_prev_5m"] = (
        panel["passenger_count"]
        .shift(5)
    )

    panel["passenger_prev_11m"] = (
        panel["passenger_count"]
        .shift(11)
    )

    panel["passenger_roll_3m"] = (
        panel["passenger_count"]
        .rolling(
            window=3,
            min_periods=3
        )
        .mean()
    )

    panel["passenger_roll_6m"] = (
        panel["passenger_count"]
        .rolling(
            window=6,
            min_periods=6
        )
        .mean()
    )

    # -----------------------------------------
    # 운항 Feature
    # -----------------------------------------

    panel["current_flight_count"] = (
        panel["flight_count"]
    )

    panel["flight_prev_1m"] = (
        panel["flight_count"]
        .shift(1)
    )

    panel["flight_roll_3m"] = (
        panel["flight_count"]
        .rolling(
            window=3,
            min_periods=3
        )
        .mean()
    )

    # -----------------------------------------
    # Target
    # 현재 월 t -> 다음 달 t+1 여객수
    # -----------------------------------------

    panel["target_next_month_passengers"] = (
        panel["passenger_count"]
        .shift(-1)
    )

    panel["target_observed"] = (
        panel["row_observed"]
        .shift(-1)
    )

    panel["target_month"] = (
        panel.index
        + pd.DateOffset(months=1)
    )

    # 실제 존재했던 현재 월만 다시 사용
    panel = panel[
        panel["row_observed"] == 1
    ].copy()

    panel = panel.reset_index()

    return panel


def main():

    print("=== 1. 데이터 로드 ===")

    base = pd.read_csv(BASE_PATH)
    coverage = pd.read_csv(COVERAGE_PATH)

    candidate_routes = get_candidate_routes(
        coverage
    )

    print(
        "ML 후보 노선 수:",
        len(candidate_routes)
    )

    print(
        "ML 후보 노선:",
        candidate_routes
    )

    # -------------------------------------------------
    # 2. 엄격한 1차 ML 후보 노선만 사용
    # -------------------------------------------------

    df = base[
        base["route"].isin(
            candidate_routes
        )
    ].copy()

    df["date"] = pd.to_datetime(
        df["year_month"],
        format="%Y-%m"
    )

    print(
        "후보 노선 원본 행 수:",
        len(df)
    )

    # -------------------------------------------------
    # 3. Route별 월 캘린더 맞춘 뒤 Feature Engineering
    # -------------------------------------------------

    engineered = []

    for route, group in df.groupby("route"):

        result = engineer_route(group)

        engineered.append(result)

    result = pd.concat(
        engineered,
        ignore_index=True
    )

    # -------------------------------------------------
    # 4. 다음 달 달력 Feature
    # -------------------------------------------------

    result["target_year"] = (
        result["target_month"].dt.year
    )

    result["target_month_num"] = (
        result["target_month"].dt.month
    )

    result["target_month_sin"] = np.sin(
        2
        * np.pi
        * result["target_month_num"]
        / 12
    )

    result["target_month_cos"] = np.cos(
        2
        * np.pi
        * result["target_month_num"]
        / 12
    )

    result["target_covid_period"] = (
        result["target_year"]
        .isin([2020, 2021])
        .astype(int)
    )

    # -------------------------------------------------
    # 5. 다음 달 한국 / 일본 공휴일
    # 공휴일은 미래 일정이 이미 알려진 정보이므로 사용 가능
    # -------------------------------------------------

    kr_holiday = build_holiday_monthly(
        KR_HOLIDAY_PATH,
        "kr"
    )

    jp_holiday = build_holiday_monthly(
        JP_HOLIDAY_PATH,
        "jp"
    )

    result = result.merge(
        kr_holiday,
        on="target_month",
        how="left",
        validate="many_to_one"
    )

    result = result.merge(
        jp_holiday,
        on="target_month",
        how="left",
        validate="many_to_one"
    )

    next_holiday_columns = [
        "next_kr_holiday_count",
        "next_kr_holiday_name_count",
        "next_kr_has_holiday",
        "next_jp_holiday_count",
        "next_jp_holiday_name_count",
        "next_jp_has_holiday",
    ]

    result[next_holiday_columns] = (
        result[next_holiday_columns]
        .fillna(0)
        .astype(int)
    )

    # -------------------------------------------------
    # 6. Target 실제 존재 여부
    # -------------------------------------------------

    result.loc[
        result["target_observed"] != 1,
        "target_next_month_passengers"
    ] = np.nan

    result["target_year_month"] = (
        result["target_month"]
        .dt.to_period("M")
        .astype(str)
    )

    # -------------------------------------------------
    # 7. 모델 학습에 필요한 필수 Feature
    # -------------------------------------------------

    model_features = [
        "current_passenger_count",
        "passenger_prev_1m",
        "passenger_prev_2m",
        "passenger_prev_5m",
        "passenger_prev_11m",
        "passenger_roll_3m",
        "passenger_roll_6m",

        "current_flight_count",
        "flight_prev_1m",
        "flight_roll_3m",

        "market_passenger_total",
        "market_passenger_flights",
        "active_passenger_airlines",

        "jpy_krw_avg",
        "jpy_krw_mom_pct",
        "jpy_krw_3m_pct",

        "next_kr_holiday_count",
        "next_jp_holiday_count",

        "target_month_sin",
        "target_month_cos",

        "target_next_month_passengers",
    ]

    # -------------------------------------------------
    # 8. 전체 Feature 파일 저장
    # -------------------------------------------------

    result = result.sort_values(
        [
            "route",
            "date"
        ]
    ).reset_index(drop=True)

    result.to_csv(
        ALL_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    # -------------------------------------------------
    # 9. ML 학습 가능 행만 생성
    # -------------------------------------------------

    training = result.dropna(
        subset=model_features
    ).copy()

    training = training.sort_values(
        [
            "target_month",
            "route"
        ]
    ).reset_index(drop=True)

    training.to_csv(
        TRAIN_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    # -------------------------------------------------
    # 10. 검증
    # -------------------------------------------------

    print("\n=== Feature Engineering 결과 ===")

    print(
        "전체 후보 행:",
        len(result)
    )

    print(
        "Target 존재 행:",
        result[
            "target_next_month_passengers"
        ].notna().sum()
    )

    print(
        "최종 ML 학습 가능 행:",
        len(training)
    )

    print(
        "학습 노선 수:",
        training["route"].nunique()
    )

    if len(training) > 0:

        print(
            "학습 Target 기간:",
            training[
                "target_year_month"
            ].min(),
            "~",
            training[
                "target_year_month"
            ].max()
        )

    print("\n노선별 학습 행 수:")

    print(
        training.groupby("route")
        .size()
        .sort_values(
            ascending=False
        )
    )

    print("\nTarget 통계:")

    print(
        training[
            "target_next_month_passengers"
        ].describe()
    )

    print("\n주요 Feature 결측치:")

    print(
        training[
            model_features
        ]
        .isna()
        .sum()
    )

    print(
        f"\n[SAVED] {ALL_OUTPUT_PATH}"
    )

    print(
        f"[SAVED] {TRAIN_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()