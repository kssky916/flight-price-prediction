from pathlib import Path
import re

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

MONTHLY_BASE_PATH = (
    ROOT_DIR
    / "data/processed/ml/route_monthly_base.csv"
)

JAPAN_FEATURE_PATH = (
    ROOT_DIR
    / "data/processed/route_features_japan.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/route_monthly_japan.csv"
)


def find_column(df, candidates):
    for col in candidates:
        if col in df.columns:
            return col

    raise KeyError(
        f"컬럼을 찾을 수 없습니다.\n"
        f"후보: {candidates}\n"
        f"현재 컬럼: {df.columns.tolist()}"
    )


def extract_airport_code(value):
    """
    도쿄 나리타(NRT) -> NRT
    간사이(KIX) -> KIX
    NRT -> NRT
    """
    if pd.isna(value):
        return None

    text = str(value).strip()

    match = re.search(r"\(([A-Z]{3})\)", text)

    if match:
        return match.group(1)

    if re.fullmatch(r"[A-Z]{3}", text):
        return text

    return None


def main():
    monthly = pd.read_csv(MONTHLY_BASE_PATH)
    japan_reference = pd.read_csv(JAPAN_FEATURE_PATH)

    destination_col = find_column(
        japan_reference,
        [
            "destination",
            "destination_airport",
            "arrival_airport",
        ],
    )

    # 기존 일본 노선 데이터의 공항명을 IATA 코드로 변환
    japan_airports = (
        japan_reference[destination_col]
        .apply(extract_airport_code)
        .dropna()
        .unique()
        .tolist()
    )

    print("일본 도착 공항 수:", len(japan_airports))
    print("일본 도착 공항 코드:", sorted(japan_airports))

    # 월별 데이터의 destination은 이미 IATA 코드
    japan = monthly[
        monthly["destination"].isin(japan_airports)
    ].copy()

    # 데이터 품질 상태
    japan["data_quality_status"] = "normal"

    japan.loc[
        (japan["passenger_count"] == 0)
        & (japan["flight_count"] == 0),
        "data_quality_status",
    ] = "inactive"

    japan.loc[
        (japan["passenger_count"] > 0)
        & (japan["flight_count"] == 0),
        "data_quality_status",
    ] = "passenger_without_flight"

    japan.loc[
        (japan["passenger_count"] == 0)
        & (japan["flight_count"] > 0),
        "data_quality_status",
    ] = "flight_without_passenger"

    japan["service_active"] = (
        japan["flight_count"] > 0
    ).astype(int)

    # 여객은 있는데 운항 0인 경우 공급 데이터 불일치로 표시
    inconsistent_mask = (
        (japan["passenger_count"] > 0)
        & (japan["flight_count"] == 0)
    )

    japan.loc[
        inconsistent_mask,
        "flight_count"
    ] = pd.NA

    # 편당 승객수 재계산
    japan["passengers_per_flight"] = (
        japan["passenger_count"]
        / japan["flight_count"]
    )

    japan = japan.sort_values(
        ["route", "year_month"]
    ).reset_index(drop=True)

    print("\n=== 일본 노선 데이터 ===")
    print("총 행 수:", len(japan))
    print("노선 수:", japan["route"].nunique())

    if len(japan) > 0:
        print(
            "기간:",
            japan["year_month"].min(),
            "~",
            japan["year_month"].max(),
        )

    print("\n노선 목록:")
    print(
        sorted(
            japan["route"]
            .dropna()
            .unique()
            .tolist()
        )
    )

    print("\n품질 상태:")
    print(
        japan["data_quality_status"]
        .value_counts()
    )

    print("\n[여객 > 0 / 운항 0]")
    print(
        japan[
            japan["data_quality_status"]
            == "passenger_without_flight"
        ][
            [
                "year_month",
                "route",
                "passenger_count",
                "flight_count",
            ]
        ].to_string(index=False)
    )

    print("\n[여객 0 / 운항 > 0] 샘플")
    print(
        japan[
            japan["data_quality_status"]
            == "flight_without_passenger"
        ][
            [
                "year_month",
                "route",
                "passenger_count",
                "flight_count",
            ]
        ]
        .head(30)
        .to_string(index=False)
    )

    japan.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\n[SAVED] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()