from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/airline_monthly_base.csv"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/ml/airline_market_monthly.csv"
)


def main():
    df = pd.read_csv(INPUT_PATH)

    print("=== 원본 ===")
    print("행 수:", len(df))
    print("항공사 수:", df["airline"].nunique())

    # -----------------------------------------------------
    # 1. 집계용 소계 행 제거
    # -----------------------------------------------------

    aggregate_names = {
        "전체 합계",
        "국적사 계",
        "외항사 계",
    }

    aggregate_mask = (
        df["airline"].isin(aggregate_names)
        | df["airline"].astype(str).str.contains(
            "합계",
            na=False
        )
    )

    print("\n제외되는 집계 행:")
    print(
        sorted(
            df.loc[
                aggregate_mask,
                "airline"
            ].unique().tolist()
        )
    )

    clean = df.loc[
        ~aggregate_mask
    ].copy()

    # -----------------------------------------------------
    # 2. 여객 운송 활동 여부
    # -----------------------------------------------------

    # 여객 수가 존재하는 항공사-월만
    # 여객시장 활동 항공사로 판단
    clean["active_passenger_airline"] = (
        clean["passenger_count"] > 0
    ).astype(int)

    # 화물전용/비여객 운항이 전체 공급량을 부풀리지 않도록
    # 여객 실적이 있는 항공사의 운항편만 별도 계산
    clean["passenger_service_flights"] = (
        clean["flight_count"].where(
            clean["passenger_count"] > 0,
            0
        )
    )

    # 참고용: 여객 실적이 없는 운항편
    clean["nonpassenger_flights"] = (
        clean["flight_count"].where(
            clean["passenger_count"] == 0,
            0
        )
    )

    # -----------------------------------------------------
    # 3. 월별 시장 지표 생성
    # -----------------------------------------------------

    monthly = (
        clean.groupby(
            "year_month",
            as_index=False
        )
        .agg(
            market_passenger_total=(
                "passenger_count",
                "sum"
            ),
            market_flight_total_all=(
                "flight_count",
                "sum"
            ),
            market_passenger_flights=(
                "passenger_service_flights",
                "sum"
            ),
            nonpassenger_flights=(
                "nonpassenger_flights",
                "sum"
            ),
            active_passenger_airlines=(
                "active_passenger_airline",
                "sum"
            ),
        )
    )

    monthly["market_passengers_per_flight"] = (
        monthly["market_passenger_total"]
        / monthly["market_passenger_flights"].replace(
            0,
            pd.NA
        )
    )

    monthly = monthly.sort_values(
        "year_month"
    ).reset_index(drop=True)

    # -----------------------------------------------------
    # 4. 품질 확인
    # -----------------------------------------------------

    print("\n=== 월별 항공시장 피처 ===")
    print("총 월 수:", len(monthly))

    print(
        "기간:",
        monthly["year_month"].min(),
        "~",
        monthly["year_month"].max()
    )

    print("\n결측치:")
    print(monthly.isna().sum())

    print("\n앞 12개월:")
    print(
        monthly.head(12)
        .to_string(index=False)
    )

    print("\n최근 12개월:")
    print(
        monthly.tail(12)
        .to_string(index=False)
    )

    # -----------------------------------------------------
    # 5. 저장
    # -----------------------------------------------------

    monthly.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig"
    )

    print(
        f"\n[SAVED] {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()