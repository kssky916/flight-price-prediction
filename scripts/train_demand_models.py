from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    mean_absolute_percentage_error,
)


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_training_table.csv"
)

RESULT_PATH = (
    ROOT_DIR
    / "data/processed/ml/model_comparison.csv"
)

PREDICTION_PATH = (
    ROOT_DIR
    / "data/processed/ml/test_predictions.csv"
)


# =========================================================
# 평가 지표
# =========================================================

def calculate_metrics(
    y_true,
    y_pred,
    model_name,
):
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    # 여객수는 음수가 될 수 없으므로
    # 음수 예측값은 0으로 보정
    y_pred = np.maximum(y_pred, 0)

    mae = mean_absolute_error(
        y_true,
        y_pred,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred,
        )
    )

    mape = (
        mean_absolute_percentage_error(
            y_true,
            y_pred,
        )
        * 100
    )

    denominator = (
        np.abs(y_true)
        + np.abs(y_pred)
    )

    smape = (
        np.mean(
            np.where(
                denominator == 0,
                0,
                2
                * np.abs(y_pred - y_true)
                / denominator,
            )
        )
        * 100
    )

    return {
        "model": model_name,
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "MAPE_pct": round(mape, 2),
        "sMAPE_pct": round(smape, 2),
    }


# =========================================================
# 실행
# =========================================================

def main():

    print("=== 1. 데이터 로드 ===")

    df = pd.read_csv(INPUT_PATH)

    df["target_date"] = pd.to_datetime(
        df["target_year_month"],
        format="%Y-%m",
    )

    print("전체 행 수:", len(df))
    print(
        "노선 수:",
        df["route"].nunique(),
    )

    print(
        "Target 기간:",
        df["target_year_month"].min(),
        "~",
        df["target_year_month"].max(),
    )

    # =====================================================
    # 2. Feature 정의
    # =====================================================

    numeric_features = [

        # 현재/과거 노선 수요
        "current_passenger_count",
        "passenger_prev_1m",
        "passenger_prev_2m",
        "passenger_prev_5m",
        "passenger_prev_11m",
        "passenger_roll_3m",
        "passenger_roll_6m",

        # 현재/과거 공급
        "current_flight_count",
        "flight_prev_1m",
        "flight_roll_3m",

        # 전체 항공시장
        "market_passenger_total",
        "market_passenger_flights",
        "active_passenger_airlines",

        # 환율
        "jpy_krw_avg",
        "jpy_krw_mom_pct",
        "jpy_krw_3m_pct",

        # 예측 대상 월 공휴일
        "next_kr_holiday_count",
        "next_jp_holiday_count",

        # 예측 대상 월 계절성
        "target_month_sin",
        "target_month_cos",

        # 코로나 특수 기간
        "target_covid_period",
    ]

    target = (
        "target_next_month_passengers"
    )

    # =====================================================
    # 3. Route 범주형 Feature
    # =====================================================

    model_df = df[
        numeric_features
        + [
            "route",
            target,
            "target_date",
            "target_year_month",
        ]
    ].copy()

    model_df = pd.get_dummies(
        model_df,
        columns=["route"],
        prefix="route",
        dtype=float,
    )

    route_features = [
        col
        for col in model_df.columns
        if col.startswith("route_")
    ]

    feature_columns = (
        numeric_features
        + route_features
    )

    # =====================================================
    # 4. 시간순 Train / Test 분리
    #
    # Train : ~ 2025-08 Target
    # Test  : 2025-09 ~ 2026-08 Target
    # =====================================================

    test_start = pd.Timestamp(
        "2025-09-01"
    )

    train = model_df[
        model_df["target_date"]
        < test_start
    ].copy()

    test = model_df[
        model_df["target_date"]
        >= test_start
    ].copy()

    print("\n=== 2. 시간순 데이터 분리 ===")

    print("Train 행:", len(train))
    print("Test 행:", len(test))

    print(
        "Train 기간:",
        train["target_year_month"].min(),
        "~",
        train["target_year_month"].max(),
    )

    print(
        "Test 기간:",
        test["target_year_month"].min(),
        "~",
        test["target_year_month"].max(),
    )

    X_train = train[
        feature_columns
    ]

    y_train = train[target]

    X_test = test[
        feature_columns
    ]

    y_test = test[target]

    results = []

    # =====================================================
    # 5. Baseline 1
    #
    # 다음 달도 현재 월과 비슷할 것이라고 예측
    # =====================================================

    naive_pred = test[
        "current_passenger_count"
    ].values

    results.append(
        calculate_metrics(
            y_test,
            naive_pred,
            "Naive_Previous_Month",
        )
    )

    # =====================================================
    # 6. Baseline 2
    #
    # 전년 동월 수요를 예측값으로 사용
    # =====================================================

    seasonal_pred = test[
        "passenger_prev_11m"
    ].values

    results.append(
        calculate_metrics(
            y_test,
            seasonal_pred,
            "Seasonal_Naive_12M",
        )
    )

    # =====================================================
    # 7. Linear Regression
    # =====================================================

    print("\n[TRAIN] Linear Regression")

    linear = LinearRegression()

    linear.fit(
        X_train,
        y_train,
    )

    linear_pred = linear.predict(
        X_test
    )

    linear_pred = np.maximum(
        linear_pred,
        0,
    )

    results.append(
        calculate_metrics(
            y_test,
            linear_pred,
            "LinearRegression",
        )
    )

    # =====================================================
    # 8. Random Forest
    # =====================================================

    print("[TRAIN] Random Forest")

    rf = RandomForestRegressor(
        n_estimators=500,
        max_depth=10,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
    )

    rf.fit(
        X_train,
        y_train,
    )

    rf_pred = rf.predict(
        X_test
    )

    results.append(
        calculate_metrics(
            y_test,
            rf_pred,
            "RandomForest",
        )
    )

    # =====================================================
    # 9. 성능 비교
    # =====================================================

    result_df = pd.DataFrame(
        results
    )

    result_df = result_df.sort_values(
        "MAE"
    ).reset_index(drop=True)

    print("\n=== 모델 성능 비교 ===")

    print(
        result_df.to_string(
            index=False
        )
    )

    # Baseline 대비 MAE 개선율
    baseline_mae = result_df.loc[
        result_df["model"]
        == "Naive_Previous_Month",
        "MAE",
    ].iloc[0]

    result_df[
        "MAE_improvement_vs_previous_month_pct"
    ] = (
        (
            baseline_mae
            - result_df["MAE"]
        )
        / baseline_mae
        * 100
    ).round(2)

    print(
        "\n=== 전월 기준모델 대비 개선율 ==="
    )

    print(
        result_df[
            [
                "model",
                "MAE",
                "MAE_improvement_vs_previous_month_pct",
            ]
        ].to_string(
            index=False
        )
    )

    # =====================================================
    # 10. Test 예측 결과 저장
    # =====================================================

    prediction_df = df[
        df["target_date"]
        >= test_start
    ][
        [
            "route",
            "target_year_month",
            "target_next_month_passengers",
        ]
    ].copy()

    prediction_df[
        "naive_previous_month"
    ] = naive_pred

    prediction_df[
        "seasonal_naive_12m"
    ] = seasonal_pred

    prediction_df[
        "linear_prediction"
    ] = linear_pred

    prediction_df[
        "random_forest_prediction"
    ] = rf_pred

    prediction_df = prediction_df.rename(
        columns={
            "target_next_month_passengers":
                "actual_passengers"
        }
    )

    # =====================================================
    # 11. Random Forest Feature Importance
    # =====================================================

    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance":
                rf.feature_importances_,
        }
    ).sort_values(
        "importance",
        ascending=False,
    )

    print(
        "\n=== Random Forest Feature Importance TOP 15 ==="
    )

    print(
        importance.head(15)
        .to_string(
            index=False
        )
    )

    # =====================================================
    # 12. 저장
    # =====================================================

    result_df.to_csv(
        RESULT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    prediction_df.to_csv(
        PREDICTION_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    importance.to_csv(
        ROOT_DIR
        / "data/processed/ml/random_forest_feature_importance.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"\n[SAVED] {RESULT_PATH}"
    )

    print(
        f"[SAVED] {PREDICTION_PATH}"
    )


if __name__ == "__main__":
    main()