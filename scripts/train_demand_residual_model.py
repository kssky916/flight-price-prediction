from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_training_table.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/residual_model_comparison.csv"
)

PREDICTION_PATH = (
    ROOT_DIR
    / "data/processed/ml/residual_model_predictions.csv"
)


# =========================================================
# 평가 함수
# =========================================================

def calculate_metrics(y_true, y_pred):

    y_true = np.asarray(
        y_true,
        dtype=float,
    ).reshape(-1)

    y_pred = np.asarray(
        y_pred,
        dtype=float,
    ).reshape(-1)

    y_pred = np.maximum(
        y_pred,
        0,
    )

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

    actual_sum = np.sum(
        np.abs(y_true)
    )

    if actual_sum > 0:
        wape = (
            np.sum(
                np.abs(
                    y_true - y_pred
                )
            )
            / actual_sum
            * 100
        )
    else:
        wape = np.nan

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
                * np.abs(
                    y_true - y_pred
                )
                / denominator
            )
        )
        * 100
    )

    return {
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "WAPE_pct": round(wape, 2),
        "sMAPE_pct": round(smape, 2),
    }


# =========================================================
# 실행
# =========================================================

def main():

    print("=== 1. 데이터 로드 ===")

    df = pd.read_csv(
        INPUT_PATH
    )

    df["target_date"] = pd.to_datetime(
        df["target_year_month"],
        format="%Y-%m",
    )

    # -----------------------------------------------------
    # 2. 변화량 Feature 생성
    # -----------------------------------------------------

    df["passenger_change_1m"] = (
        df["current_passenger_count"]
        - df["passenger_prev_1m"]
    )

    df["passenger_change_pct_1m"] = (
        (
            df["current_passenger_count"]
            - df["passenger_prev_1m"]
        )
        / df["passenger_prev_1m"]
        .replace(0, np.nan)
    )

    df["flight_change_1m"] = (
        df["current_flight_count"]
        - df["flight_prev_1m"]
    )

    df["flight_change_pct_1m"] = (
        (
            df["current_flight_count"]
            - df["flight_prev_1m"]
        )
        / df["flight_prev_1m"]
        .replace(0, np.nan)
    )

    # 너무 큰 비율값 방지
    df["passenger_change_pct_1m"] = (
        df["passenger_change_pct_1m"]
        .clip(-3, 3)
        .fillna(0)
    )

    df["flight_change_pct_1m"] = (
        df["flight_change_pct_1m"]
        .clip(-3, 3)
        .fillna(0)
    )

    # -----------------------------------------------------
    # 3. Residual Target
    #
    # 다음 달 - 현재 달
    # -----------------------------------------------------

    df["target_change"] = (
        df["target_next_month_passengers"]
        - df["current_passenger_count"]
    )

    # -----------------------------------------------------
    # 4. Feature 정의
    # -----------------------------------------------------

    numeric_features = [

        # 현재 수요 수준
        "current_passenger_count",

        # 최근 변화
        "passenger_change_1m",
        "passenger_change_pct_1m",

        # 수요 이동평균
        "passenger_roll_3m",
        "passenger_roll_6m",

        # 과거 계절성
        "passenger_prev_11m",

        # 공급
        "current_flight_count",
        "flight_change_1m",
        "flight_change_pct_1m",
        "flight_roll_3m",

        # 전체 시장
        "market_passenger_total",
        "market_passenger_flights",
        "active_passenger_airlines",

        # 환율
        "jpy_krw_avg",
        "jpy_krw_mom_pct",
        "jpy_krw_3m_pct",

        # 다음 달 공휴일
        "next_kr_holiday_count",
        "next_jp_holiday_count",

        # 다음 달 계절성
        "target_month_sin",
        "target_month_cos",

        "target_covid_period",
    ]

    # -----------------------------------------------------
    # 5. Route One-Hot
    # -----------------------------------------------------

    model_df = df[
        numeric_features
        + [
            "route",
            "target_change",
            "target_next_month_passengers",
            "current_passenger_count",
            "target_date",
            "target_year_month",
        ]
    ].copy()

    # 중복 컬럼 제거
    model_df = model_df.loc[
        :,
        ~model_df.columns.duplicated()
    ]

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

    # -----------------------------------------------------
    # 6. 시간순 분리
    # -----------------------------------------------------

    validation_start = pd.Timestamp(
        "2024-09-01"
    )

    test_start = pd.Timestamp(
        "2025-09-01"
    )

    inner_train = model_df[
        model_df["target_date"]
        < validation_start
    ].copy()

    validation = model_df[
        (
            model_df["target_date"]
            >= validation_start
        )
        & (
            model_df["target_date"]
            < test_start
        )
    ].copy()

    full_train = model_df[
        model_df["target_date"]
        < test_start
    ].copy()

    test = model_df[
        model_df["target_date"]
        >= test_start
    ].copy()

    print(
        "Inner Train:",
        len(inner_train)
    )

    print(
        "Validation:",
        len(validation)
    )

    print(
        "Full Train:",
        len(full_train)
    )

    print(
        "Final Test:",
        len(test)
    )

    # -----------------------------------------------------
    # 7. Ridge alpha Validation
    # -----------------------------------------------------

    alphas = [
        0.1,
        1.0,
        10.0,
        100.0,
        1000.0,
    ]

    alpha_results = []

    X_inner = inner_train[
        feature_columns
    ]

    y_inner = inner_train[
        "target_change"
    ]

    X_val = validation[
        feature_columns
    ]

    y_val_actual = validation[
        "target_next_month_passengers"
    ]

    current_val = validation[
        "current_passenger_count"
    ].values

    print(
        "\n=== Residual Ridge Validation ==="
    )

    for alpha in alphas:

        model = Pipeline(
            [
                (
                    "scaler",
                    StandardScaler(),
                ),
                (
                    "model",
                    Ridge(
                        alpha=alpha
                    ),
                ),
            ]
        )

        model.fit(
            X_inner,
            y_inner,
        )

        predicted_change = model.predict(
            X_val
        )

        predicted_passengers = (
            current_val
            + predicted_change
        )

        score = calculate_metrics(
            y_val_actual,
            predicted_passengers,
        )

        alpha_results.append(
            {
                "alpha": alpha,
                **score,
            }
        )

    alpha_df = pd.DataFrame(
        alpha_results
    ).sort_values(
        "MAE"
    )

    print(
        alpha_df.to_string(
            index=False
        )
    )

    best_alpha = float(
        alpha_df.iloc[0]["alpha"]
    )

    print(
        "\n선택된 alpha:",
        best_alpha
    )

    # -----------------------------------------------------
    # 8. Final Train / Test
    # -----------------------------------------------------

    X_train = full_train[
        feature_columns
    ]

    y_train_change = full_train[
        "target_change"
    ]

    X_test = test[
        feature_columns
    ]

    y_test = test[
        "target_next_month_passengers"
    ]

    current_test = test[
        "current_passenger_count"
    ].values

    results = []
    predictions = {}

    # -----------------------------------------------------
    # Baseline
    # -----------------------------------------------------

    naive_prediction = (
        current_test.copy()
    )

    predictions[
        "naive_previous_month"
    ] = naive_prediction

    results.append(
        {
            "model":
                "Naive_Previous_Month",
            **calculate_metrics(
                y_test,
                naive_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # Residual Linear Regression
    # -----------------------------------------------------

    print(
        "\n[TRAIN] Residual Linear Regression"
    )

    linear = Pipeline(
        [
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "model",
                LinearRegression(),
            ),
        ]
    )

    linear.fit(
        X_train,
        y_train_change,
    )

    predicted_change = linear.predict(
        X_test
    )

    linear_prediction = (
        current_test
        + predicted_change
    )

    predictions[
        "residual_linear"
    ] = linear_prediction

    results.append(
        {
            "model":
                "Residual_Linear",
            **calculate_metrics(
                y_test,
                linear_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # Residual Ridge
    # -----------------------------------------------------

    print(
        "[TRAIN] Residual Ridge"
    )

    ridge = Pipeline(
        [
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "model",
                Ridge(
                    alpha=best_alpha
                ),
            ),
        ]
    )

    ridge.fit(
        X_train,
        y_train_change,
    )

    predicted_change = ridge.predict(
        X_test
    )

    ridge_prediction = (
        current_test
        + predicted_change
    )

    predictions[
        "residual_ridge"
    ] = ridge_prediction

    results.append(
        {
            "model":
                f"Residual_Ridge_{best_alpha}",
            **calculate_metrics(
                y_test,
                ridge_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # Residual Random Forest
    # -----------------------------------------------------

    print(
        "[TRAIN] Residual Random Forest"
    )

    rf = RandomForestRegressor(
        n_estimators=500,
        max_depth=6,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )

    rf.fit(
        X_train,
        y_train_change,
    )

    predicted_change = rf.predict(
        X_test
    )

    rf_prediction = (
        current_test
        + predicted_change
    )

    predictions[
        "residual_rf"
    ] = rf_prediction

    results.append(
        {
            "model":
                "Residual_RandomForest",
            **calculate_metrics(
                y_test,
                rf_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # 9. 전체 결과
    # -----------------------------------------------------

    result_df = pd.DataFrame(
        results
    ).sort_values(
        "MAE"
    ).reset_index(
        drop=True
    )

    baseline_mae = (
        result_df.loc[
            result_df["model"]
            == "Naive_Previous_Month",
            "MAE"
        ].iloc[0]
    )

    result_df[
        "MAE_improvement_vs_naive_pct"
    ] = (
        (
            baseline_mae
            - result_df["MAE"]
        )
        / baseline_mae
        * 100
    ).round(2)

    print(
        "\n=== Residual Model Final Test ==="
    )

    print(
        result_df.to_string(
            index=False
        )
    )

    # -----------------------------------------------------
    # 10. 노선별 성능
    # -----------------------------------------------------

    prediction_df = df[
        df["target_date"]
        >= test_start
    ][
        [
            "route",
            "target_year_month",
            "target_next_month_passengers",
            "current_passenger_count",
        ]
    ].copy()

    prediction_df = prediction_df.reset_index(
        drop=True
    )

    prediction_df = prediction_df.rename(
        columns={
            "target_next_month_passengers":
                "actual_passengers"
        }
    )

    for name, values in predictions.items():
        prediction_df[name] = values

    print(
        "\n=== Best Residual Model 노선별 비교 ==="
    )

    best_model_name = result_df.iloc[0][
        "model"
    ]

    if best_model_name == "Residual_Linear":
        best_column = "residual_linear"

    elif best_model_name.startswith(
        "Residual_Ridge"
    ):
        best_column = "residual_ridge"

    elif best_model_name == (
        "Residual_RandomForest"
    ):
        best_column = "residual_rf"

    else:
        best_column = (
            "naive_previous_month"
        )

    route_results = []

    for route, group in prediction_df.groupby(
        "route"
    ):

        naive_score = calculate_metrics(
            group["actual_passengers"],
            group[
                "naive_previous_month"
            ],
        )

        best_score = calculate_metrics(
            group["actual_passengers"],
            group[best_column],
        )

        improvement = (
            (
                naive_score["MAE"]
                - best_score["MAE"]
            )
            / naive_score["MAE"]
            * 100
            if naive_score["MAE"] > 0
            else np.nan
        )

        route_results.append(
            {
                "route": route,
                "naive_MAE":
                    naive_score["MAE"],
                "model_MAE":
                    best_score["MAE"],
                "model_WAPE_pct":
                    best_score["WAPE_pct"],
                "improvement_pct":
                    round(
                        improvement,
                        2,
                    ),
            }
        )

    route_df = pd.DataFrame(
        route_results
    ).sort_values(
        "improvement_pct",
        ascending=False,
    )

    print(
        route_df.to_string(
            index=False
        )
    )

    print(
        "\n개선 노선 수:",
        (
            route_df[
                "improvement_pct"
            ] > 0
        ).sum(),
        "/",
        len(route_df),
    )

    # -----------------------------------------------------
    # 11. 저장
    # -----------------------------------------------------

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    prediction_df.to_csv(
        PREDICTION_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\n[SAVED]",
        OUTPUT_PATH
    )

    print(
        "[SAVED]",
        PREDICTION_PATH
    )


if __name__ == "__main__":
    main()