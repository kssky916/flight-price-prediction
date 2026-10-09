from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/route_monthly_japan.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/japan_route_coverage.csv"
)


def main():
    df = pd.read_csv(INPUT_PATH)

    df["month"] = pd.to_datetime(
        df["year_month"],
        format="%Y-%m"
    )

    results = []

    for route, group in df.groupby("route"):
        group = group.sort_values("month")

        first_month = group["month"].min()
        last_month = group["month"].max()

        expected_months = pd.date_range(
            first_month,
            last_month,
            freq="MS",
        )

        actual_months = set(group["month"])
        missing_months = [
            month
            for month in expected_months
            if month not in actual_months
        ]

        expected_count = len(expected_months)
        actual_count = len(group)

        coverage_rate = (
            actual_count / expected_count
            if expected_count > 0
            else 0
        )

        recent_start = pd.Timestamp("2025-09-01")
        recent_end = pd.Timestamp("2026-08-01")

        recent = group[
            (group["month"] >= recent_start)
            & (group["month"] <= recent_end)
        ]

        results.append(
            {
                "route": route,
                "first_month": first_month.strftime("%Y-%m"),
                "last_month": last_month.strftime("%Y-%m"),
                "observations": actual_count,
                "expected_months": expected_count,
                "missing_months": len(missing_months),
                "coverage_rate": round(
                    coverage_rate,
                    4
                ),
                "recent_12m_observations": len(recent),
                "passenger_total": int(
                    group["passenger_count"].sum()
                ),
                "missing_month_list": ",".join(
                    month.strftime("%Y-%m")
                    for month in missing_months
                ),
            }
        )

    result = pd.DataFrame(results)

    result["ml_candidate"] = (
        (result["observations"] >= 36)
        & (result["coverage_rate"] >= 0.70)
        & (result["recent_12m_observations"] >= 10)
    )

    result = result.sort_values(
        [
            "ml_candidate",
            "observations",
            "passenger_total",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )

    print("\n=== 노선 시계열 커버리지 ===")
    print(
        result[
            [
                "route",
                "observations",
                "expected_months",
                "missing_months",
                "coverage_rate",
                "recent_12m_observations",
                "ml_candidate",
            ]
        ].to_string(index=False)
    )

    print("\nML 후보 노선 수:")
    print(result["ml_candidate"].sum())

    print("\nML 후보 노선:")
    print(
        result[
            result["ml_candidate"]
        ]["route"].tolist()
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\n[SAVED] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()