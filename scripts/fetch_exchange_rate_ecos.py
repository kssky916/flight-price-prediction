from pathlib import Path
import os

import pandas as pd
import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]

DAILY_OUTPUT = (
    ROOT_DIR
    / "data/processed/processed_exchange_rates_daily_ecos.csv"
)

MONTHLY_OUTPUT = (
    ROOT_DIR
    / "data/processed/ml/exchange_rate_monthly.csv"
)


load_dotenv()

API_KEY = os.getenv("ECOS_API_KEY")

if not API_KEY:
    raise ValueError(
        "ECOS_API_KEY가 .env에 없습니다."
    )


STAT_CODE = "731Y001"
ITEM_CODE = "0000002"

START_DATE = "20200101"
END_DATE = "20260831"


def fetch_ecos():
    rows = []

    # 전체 건수 확인
    url = (
        f"https://ecos.bok.or.kr/api/"
        f"StatisticSearch/{API_KEY}/json/kr/"
        f"1/1/"
        f"{STAT_CODE}/D/"
        f"{START_DATE}/{END_DATE}/"
        f"{ITEM_CODE}"
    )

    response = requests.get(
        url,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    if "StatisticSearch" not in data:
        raise RuntimeError(
            f"ECOS 응답 오류: {data}"
        )

    total_count = int(
        data["StatisticSearch"]["list_total_count"]
    )

    print("전체 환율 데이터 건수:", total_count)

    page_size = 1000

    for start in range(
        1,
        total_count + 1,
        page_size,
    ):
        end = min(
            start + page_size - 1,
            total_count,
        )

        print(
            f"[FETCH] {start} ~ {end}"
        )

        url = (
            f"https://ecos.bok.or.kr/api/"
            f"StatisticSearch/{API_KEY}/json/kr/"
            f"{start}/{end}/"
            f"{STAT_CODE}/D/"
            f"{START_DATE}/{END_DATE}/"
            f"{ITEM_CODE}"
        )

        response = requests.get(
            url,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        if "StatisticSearch" not in data:
            raise RuntimeError(
                f"ECOS 응답 오류: {data}"
            )

        rows.extend(
            data["StatisticSearch"]["row"]
        )

    return pd.DataFrame(rows)


def main():
    DAILY_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MONTHLY_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = fetch_ecos()

    # 날짜
    df["base_date"] = pd.to_datetime(
        df["TIME"],
        format="%Y%m%d",
    )

    # 100엔당 원화
    df["jpy_krw_rate"] = pd.to_numeric(
        df["DATA_VALUE"],
        errors="coerce",
    )

    daily = df[
        [
            "base_date",
            "jpy_krw_rate",
        ]
    ].dropna()

    daily = (
        daily
        .drop_duplicates("base_date")
        .sort_values("base_date")
        .reset_index(drop=True)
    )

    daily["year_month"] = (
        daily["base_date"]
        .dt.to_period("M")
        .astype(str)
    )

    # 월별 환율 피처
    monthly = (
        daily.groupby(
            "year_month",
            as_index=False,
        )
        .agg(
            jpy_krw_avg=(
                "jpy_krw_rate",
                "mean",
            ),
            jpy_krw_min=(
                "jpy_krw_rate",
                "min",
            ),
            jpy_krw_max=(
                "jpy_krw_rate",
                "max",
            ),
            jpy_krw_end=(
                "jpy_krw_rate",
                "last",
            ),
        )
    )

    monthly["jpy_krw_mom_pct"] = (
        monthly["jpy_krw_avg"]
        .pct_change()
        * 100
    )

    monthly["jpy_krw_3m_pct"] = (
        monthly["jpy_krw_avg"]
        .pct_change(3)
        * 100
    )

    daily.to_csv(
        DAILY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    monthly.to_csv(
        MONTHLY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n=== 일별 환율 ===")
    print("행 수:", len(daily))
    print(
        "기간:",
        daily["base_date"].min(),
        "~",
        daily["base_date"].max(),
    )

    print("\n=== 월별 환율 ===")
    print("행 수:", len(monthly))
    print(
        "기간:",
        monthly["year_month"].min(),
        "~",
        monthly["year_month"].max(),
    )

    print("\n결측치:")
    print(monthly.isna().sum())

    print("\n최근 12개월:")
    print(
        monthly.tail(12)
        .to_string(index=False)
    )

    print(
        "\n[SAVED]",
        DAILY_OUTPUT,
    )

    print(
        "[SAVED]",
        MONTHLY_OUTPUT,
    )


if __name__ == "__main__":
    main()