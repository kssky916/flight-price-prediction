from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/test_predictions.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/route_model_performance.csv"
)


MODELS = {
    "Naive_Previous_Month":
        "naive_previous_month",

    "Seasonal_Naive_12M":
        "seasonal_naive_12m",

    "LinearRegression":
        "linear_prediction",

    "RandomForest":
        "random_forest_prediction",
}


def calculate_metrics(
    y_true,
    y_pred,
):
    y_true = np.asarray(
        y_true,
        dtype=float
    )

    y_pred = np.asarray(
        y_pred,
        dtype=float
    )

    y_pred = np.maximum(
        y_pred,
        0
    )

    mae = mean_absolute_error(
        y_true,
        y_pred
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred
        )
    )

    # WAPE
    denominator = np.sum(
        np.abs(y_true)
    )

    if denominator > 0:
        wape = (
            np.sum(
                np.abs(
                    y_true - y_pred
                )
            )
            / denominator
            * 100
        )
    else:
        wape = np.nan

    # sMAPE
    smape_denominator = (
        np.abs(y_true)
        + np.abs(y_pred)
    )

    smape = (
        np.mean(
            np.where(
                smape_denominator == 0,
                0,
                2
                * np.abs(
                    y_pred - y_true
                )
                / smape_denominator
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


def main():

    df = pd.read_csv(
        INPUT_PATH
    )

    print("=== Test 데이터 ===")

    print(
        "행 수:",
        len(df)
    )

    print(
        "노선 수:",
        df["route"].nunique()
    )

    results = []

    for route, group in df.groupby(
        "route"
    ):

        actual = group[
            "actual_passengers"
        ]

        naive_mae = None

        route_results = []

        for model_name, column in MODELS.items():

            metrics = calculate_metrics(
                actual,
                group[column]
            )

            row = {
                "route": route,
                "model": model_name,
                "test_months":
                    len(group),
                "actual_mean":
                    round(
                        actual.mean(),
                        2
                    ),
                **metrics,
            }

            if (
                model_name
                == "Naive_Previous_Month"
            ):
                naive_mae = metrics["MAE"]

            route_results.append(row)

        # 기준모델 대비 개선율
        for row in route_results:

            if naive_mae > 0:

                row[
                    "MAE_improvement_vs_naive_pct"
                ] = round(
                    (
                        naive_mae
                        - row["MAE"]
                    )
                    / naive_mae
                    * 100,
                    2,
                )

            else:
                row[
                    "MAE_improvement_vs_naive_pct"
                ] = np.nan

            results.append(row)

    result = pd.DataFrame(
        results
    )

    # -----------------------------------------
    # Linear Regression 노선별 결과
    # -----------------------------------------

    linear = result[
        result["model"]
        == "LinearRegression"
    ].copy()

    linear = linear.sort_values(
        "MAE_improvement_vs_naive_pct",
        ascending=False
    )

    print(
        "\n=== Linear Regression 노선별 성능 ==="
    )

    print(
        linear[
            [
                "route",
                "test_months",
                "actual_mean",
                "MAE",
                "WAPE_pct",
                "sMAPE_pct",
                "MAE_improvement_vs_naive_pct",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nLinear Regression이 전월 기준모델보다 좋은 노선:"
    )

    better = linear[
        linear[
            "MAE_improvement_vs_naive_pct"
        ] > 0
    ]

    print(
        better["route"]
        .tolist()
    )

    print(
        "\n개선 노선 수:",
        len(better),
        "/",
        linear["route"].nunique(),
    )

    # -----------------------------------------
    # 모델별 평균
    # -----------------------------------------

    summary = (
        result.groupby(
            "model",
            as_index=False
        )
        .agg(
            route_avg_MAE=(
                "MAE",
                "mean"
            ),
            route_avg_WAPE=(
                "WAPE_pct",
                "mean"
            ),
            route_avg_sMAPE=(
                "sMAPE_pct",
                "mean"
            ),
        )
        .sort_values(
            "route_avg_MAE"
        )
    )

    print(
        "\n=== 노선별 성능을 동일 가중치로 평균 ==="
    )

    print(
        summary.to_string(
            index=False
        )
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"\n[SAVED] {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()