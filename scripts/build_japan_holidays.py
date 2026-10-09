from pathlib import Path

import pandas as pd
import holidays


ROOT_DIR = Path(__file__).resolve().parents[1]

OUTPUT_PATH = (
    ROOT_DIR
    / "data/processed/japan_holidays_clean.csv"
)


def main():

    # 일본 공휴일 2020~2026
    jp_holidays = holidays.Japan(
        years=range(2020, 2027)
    )

    rows = []

    for holiday_date, holiday_name in sorted(
        jp_holidays.items()
    ):
        rows.append(
            {
                "holiday_date": holiday_date,
                "year": holiday_date.year,
                "month": holiday_date.month,
                "day": holiday_date.day,
                "weekday": holiday_date.strftime("%A"),
                "holiday_name": holiday_name,
                "is_holiday": "Y",
                "country": "JP",
            }
        )

    df = pd.DataFrame(rows)

    df["holiday_date"] = pd.to_datetime(
        df["holiday_date"]
    )

    df = (
        df.drop_duplicates(
            subset=[
                "holiday_date",
                "holiday_name",
            ]
        )
        .sort_values("holiday_date")
        .reset_index(drop=True)
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("일본 공휴일 저장:", OUTPUT_PATH)
    print("전체 행 수:", len(df))

    print(
        "연도 범위:",
        df["year"].min(),
        "~",
        df["year"].max(),
    )

    print("\n연도별 공휴일 수:")
    print(
        df.groupby("year").size()
    )

    print("\n샘플:")
    print(
        df.head(30)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()