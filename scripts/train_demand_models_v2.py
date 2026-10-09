from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import TransformedTargetRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# =========================================================
# 경로
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/ml_training_table.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/model_comparison_v2.csv"
)

PREDICTION_PATH = (
    ROOT_DIR
    / "data/processed/ml/test_predictions_v2.csv"
)

RIDGE_VALIDATION_PATH = (
    ROOT_DIR
    / "data/processed/ml/ridge_validation.csv"
)

RIDGE_ROUTE_PATH = (
    ROOT_DIR
    / "data/processed/ml/ridge_route_performance.csv"
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

    # 여객수는 음수가 될 수 없음
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

    # WAPE
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

    # sMAPE
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
# log1p Target 모델 생성
# =========================================================

def make_log_model(regressor):

    pipeline = Pipeline(
        [
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "regressor",
                regressor,
            ),
        ]
    )

    model = TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
    )

    return model


# =========================================================
# 실행
# =========================================================

def main():

    # -----------------------------------------------------
    # 1. 데이터 로드
    # -----------------------------------------------------

    print("=== 1. 데이터 로드 ===")

    df = pd.read_csv(
        INPUT_PATH
    )

    df["target_date"] = pd.to_datetime(
        df["target_year_month"],
        format="%Y-%m",
    )

    print(
        "전체 행 수:",
        len(df),
    )

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

    # -----------------------------------------------------
    # 2. Feature 정의
    # -----------------------------------------------------

    numeric_features = [

        # 현재 / 과거 노선 수요
        "current_passenger_count",
        "passenger_prev_1m",
        "passenger_prev_2m",
        "passenger_prev_5m",
        "passenger_prev_11m",
        "passenger_roll_3m",
        "passenger_roll_6m",

        # 현재 / 과거 공급
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

        # 다음 달 한국 / 일본 공휴일
        "next_kr_holiday_count",
        "next_jp_holiday_count",

        # 다음 달 계절성
        "target_month_sin",
        "target_month_cos",

        # 코로나 특수 기간
        "target_covid_period",
    ]

    target = (
        "target_next_month_passengers"
    )

    # -----------------------------------------------------
    # 3. 필요한 컬럼만 가져오기
    #
    # 중요:
    # current_passenger_count,
    # passenger_prev_11m은 이미 numeric_features에 있으므로
    # 여기서 다시 추가하지 않음.
    # -----------------------------------------------------

    model_df = df[
        numeric_features
        + [
            "route",
            target,
            "target_date",
            "target_year_month",
        ]
    ].copy()

    # -----------------------------------------------------
    # 4. Route One-Hot Encoding
    # -----------------------------------------------------

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

    print(
        "모델 Feature 수:",
        len(feature_columns),
    )

    # -----------------------------------------------------
    # 5. 시간순 데이터 분리
    #
    # Inner Train : ~ 2024-08
    # Validation  : 2024-09 ~ 2025-08
    # Final Test  : 2025-09 ~ 2026-08
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
        "\n=== 데이터 분리 ==="
    )

    print(
        "Inner Train:",
        len(inner_train),
    )

    print(
        "Validation:",
        len(validation),
    )

    print(
        "Full Train:",
        len(full_train),
    )

    print(
        "Final Test:",
        len(test),
    )

    print(
        "Validation 기간:",
        validation["target_year_month"].min(),
        "~",
        validation["target_year_month"].max(),
    )

    print(
        "Final Test 기간:",
        test["target_year_month"].min(),
        "~",
        test["target_year_month"].max(),
    )

    # -----------------------------------------------------
    # 6. Ridge alpha 선택
    # -----------------------------------------------------

    X_inner = inner_train[
        feature_columns
    ]

    y_inner = inner_train[
        target
    ]

    X_validation = validation[
        feature_columns
    ]

    y_validation = validation[
        target
    ]

    alphas = [
        0.1,
        1.0,
        10.0,
        100.0,
        1000.0,
    ]

    alpha_results = []

    print(
        "\n=== Ridge alpha Validation ==="
    )

    for alpha in alphas:

        model = make_log_model(
            Ridge(
                alpha=alpha
            )
        )

        model.fit(
            X_inner,
            y_inner,
        )

        prediction = model.predict(
            X_validation
        )

        prediction = np.maximum(
            prediction,
            0,
        )

        score = calculate_metrics(
            y_validation,
            prediction,
        )

        alpha_results.append(
            {
                "alpha": alpha,
                **score,
            }
        )

    alpha_df = pd.DataFrame(
        alpha_results
    )

    alpha_df = alpha_df.sort_values(
        "MAE"
    ).reset_index(
        drop=True
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
        best_alpha,
    )

    # -----------------------------------------------------
    # 7. 최종 Train / Test
    # -----------------------------------------------------

    X_train = full_train[
        feature_columns
    ]

    y_train = full_train[
        target
    ]

    X_test = test[
        feature_columns
    ]

    y_test = test[
        target
    ]

    results = []
    predictions = {}

    # -----------------------------------------------------
    # 8. Baseline 1
    # 전월 여객수
    # -----------------------------------------------------

    naive_prediction = (
        test["current_passenger_count"]
        .to_numpy(
            dtype=float
        )
        .reshape(-1)
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
    # 9. Baseline 2
    # 전년 동월 여객수
    # -----------------------------------------------------

    seasonal_prediction = (
        test["passenger_prev_11m"]
        .to_numpy(
            dtype=float
        )
        .reshape(-1)
    )

    predictions[
        "seasonal_naive_12m"
    ] = seasonal_prediction

    results.append(
        {
            "model":
                "Seasonal_Naive_12M",
            **calculate_metrics(
                y_test,
                seasonal_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # 10. Raw Linear Regression
    # -----------------------------------------------------

    print(
        "\n[TRAIN] Raw Linear Regression"
    )

    raw_linear = Pipeline(
        [
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "regressor",
                LinearRegression(),
            ),
        ]
    )

    raw_linear.fit(
        X_train,
        y_train,
    )

    linear_raw_prediction = (
        raw_linear.predict(
            X_test
        )
    )

    linear_raw_prediction = np.maximum(
        linear_raw_prediction,
        0,
    )

    predictions[
        "linear_raw"
    ] = linear_raw_prediction

    results.append(
        {
            "model":
                "Linear_Raw_Target",
            **calculate_metrics(
                y_test,
                linear_raw_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # 11. Log Linear Regression
    # -----------------------------------------------------

    print(
        "[TRAIN] Log Linear Regression"
    )

    log_linear = make_log_model(
        LinearRegression()
    )

    log_linear.fit(
        X_train,
        y_train,
    )

    linear_log_prediction = (
        log_linear.predict(
            X_test
        )
    )

    linear_log_prediction = np.maximum(
        linear_log_prediction,
        0,
    )

    predictions[
        "linear_log"
    ] = linear_log_prediction

    results.append(
        {
            "model":
                "Linear_Log_Target",
            **calculate_metrics(
                y_test,
                linear_log_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # 12. Log Ridge
    # -----------------------------------------------------

    print(
        "[TRAIN] Log Ridge"
    )

    ridge_log = make_log_model(
        Ridge(
            alpha=best_alpha
        )
    )

    ridge_log.fit(
        X_train,
        y_train,
    )

    ridge_log_prediction = (
        ridge_log.predict(
            X_test
        )
    )

    ridge_log_prediction = np.maximum(
        ridge_log_prediction,
        0,
    )

    predictions[
        "ridge_log"
    ] = ridge_log_prediction

    results.append(
        {
            "model":
                f"Ridge_Log_alpha_{best_alpha}",
            **calculate_metrics(
                y_test,
                ridge_log_prediction,
            ),
        }
    )

    # -----------------------------------------------------
    # 13. Final Test 전체 성능 비교
    # -----------------------------------------------------

    result_df = pd.DataFrame(
        results
    )

    result_df = result_df.sort_values(
        "MAE"
    ).reset_index(
        drop=True
    )

    baseline_mae = (
        result_df.loc[
            result_df["model"]
            == "Naive_Previous_Month",
            "MAE",
        ]
        .iloc[0]
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
        "\n=== Final Test 결과 ==="
    )

    print(
        result_df.to_string(
            index=False
        )
    )

    # -----------------------------------------------------
    # 14. Test 예측 결과 저장용 데이터
    # -----------------------------------------------------

    test_mask = (
        df["target_date"]
        >= test_start
    )

    prediction_df = df.loc[
        test_mask,
        [
            "route",
            "target_year_month",
            "target_next_month_passengers",
        ],
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

    prediction_df[
        "naive_previous_month"
    ] = predictions[
        "naive_previous_month"
    ]

    prediction_df[
        "seasonal_naive_12m"
    ] = predictions[
        "seasonal_naive_12m"
    ]

    prediction_df[
        "linear_raw"
    ] = predictions[
        "linear_raw"
    ]

    prediction_df[
        "linear_log"
    ] = predictions[
        "linear_log"
    ]

    prediction_df[
        "ridge_log"
    ] = predictions[
        "ridge_log"
    ]

    # -----------------------------------------------------
    # 15. Ridge 노선별 성능
    # -----------------------------------------------------

    print(
        "\n=== Ridge Log 노선별 성능 ==="
    )

    route_results = []

    for route, group in prediction_df.groupby(
        "route"
    ):

        naive_score = calculate_metrics(
            group["actual_passengers"],
            group["naive_previous_month"],
        )

        ridge_score = calculate_metrics(
            group["actual_passengers"],
            group["ridge_log"],
        )

        if naive_score["MAE"] > 0:

            improvement = (
                (
                    naive_score["MAE"]
                    - ridge_score["MAE"]
                )
                / naive_score["MAE"]
                * 100
            )

        else:
            improvement = np.nan

        route_results.append(
            {
                "route": route,

                "test_months":
                    len(group),

                "actual_mean":
                    round(
                        group[
                            "actual_passengers"
                        ].mean(),
                        2,
                    ),

                "naive_MAE":
                    naive_score["MAE"],

                "ridge_MAE":
                    ridge_score["MAE"],

                "ridge_RMSE":
                    ridge_score["RMSE"],

                "ridge_WAPE_pct":
                    ridge_score[
                        "WAPE_pct"
                    ],

                "ridge_sMAPE_pct":
                    ridge_score[
                        "sMAPE_pct"
                    ],

                "improvement_pct":
                    round(
                        improvement,
                        2,
                    ),
            }
        )

    route_df = pd.DataFrame(
        route_results
    )

    route_df = route_df.sort_values(
        "improvement_pct",
        ascending=False,
    ).reset_index(
        drop=True
    )

    print(
        route_df.to_string(
            index=False
        )
    )

    improved_count = (
        route_df[
            "improvement_pct"
        ] > 0
    ).sum()

    print(
        "\nRidge가 개선한 노선 수:",
        improved_count,
        "/",
        len(route_df),
    )

    # -----------------------------------------------------
    # 16. 각 모델이 몇 개 노선을 개선했는지 추가 확인
    # -----------------------------------------------------

    print(
        "\n=== 모델별 노선 개선 개수 ==="
    )

    model_columns = {
        "Linear_Raw_Target":
            "linear_raw",

        "Linear_Log_Target":
            "linear_log",

        f"Ridge_Log_alpha_{best_alpha}":
            "ridge_log",
    }

    route_model_summary = []

    for model_name, prediction_column in (
        model_columns.items()
    ):

        improvement_count = 0

        for route, group in (
            prediction_df.groupby("route")
        ):

            naive_mae = (
                calculate_metrics(
                    group[
                        "actual_passengers"
                    ],
                    group[
                        "naive_previous_month"
                    ],
                )["MAE"]
            )

            model_mae = (
                calculate_metrics(
                    group[
                        "actual_passengers"
                    ],
                    group[
                        prediction_column
                    ],
                )["MAE"]
            )

            if model_mae < naive_mae:
                improvement_count += 1

        route_model_summary.append(
            {
                "model": model_name,
                "improved_routes":
                    improvement_count,
                "total_routes":
                    prediction_df[
                        "route"
                    ].nunique(),
            }
        )

    route_model_summary_df = (
        pd.DataFrame(
            route_model_summary
        )
    )

    print(
        route_model_summary_df
        .to_string(
            index=False
        )
    )

    # -----------------------------------------------------
    # 17. 저장
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

    alpha_df.to_csv(
        RIDGE_VALIDATION_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    route_df.to_csv(
        RIDGE_ROUTE_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\n[SAVED]",
        OUTPUT_PATH,
    )

    print(
        "[SAVED]",
        PREDICTION_PATH,
    )

    print(
        "[SAVED]",
        RIDGE_VALIDATION_PATH,
    )

    print(
        "[SAVED]",
        RIDGE_ROUTE_PATH,
    )


if __name__ == "__main__":
    main()