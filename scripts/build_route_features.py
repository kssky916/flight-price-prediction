from pathlib import Path
import pandas as pd

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

ROUTE_PATH = PROCESSED_DIR / "processed_route_stats_japan.csv"
COMPETITION_PATH = PROCESSED_DIR / "processed_icn_route_competition_japan.csv"
COUNTRY_PATH = PROCESSED_DIR / "processed_country_stats_japan.csv"
EXCHANGE_PATH = PROCESSED_DIR / "processed_exchange_rates_daily.csv"
HOLIDAY_PATH = PROCESSED_DIR / "processed_holidays_clean.csv"

OUTPUT_PATH = PROCESSED_DIR / "route_features_japan.csv"


def check_file(path):
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")


def get_latest_exchange_by_year(exchange_df):
    exchange_df["base_date"] = pd.to_datetime(exchange_df["base_date"], errors="coerce")
    exchange_df = exchange_df.dropna(subset=["base_date"]).copy()

    exchange_df = exchange_df.sort_values("base_date")

    yearly = (
        exchange_df.groupby("year", as_index=False)
        .tail(1)
        .copy()
    )

    return yearly[
        [
            "year",
            "jpy_krw_rate",
            "jpy_krw_change_rate_7d",
            "jpy_krw_change_rate_30d",
            "jpy_krw_change_rate_90d",
        ]
    ]


def get_holiday_count_by_year(holiday_df):
    holiday_df["holiday_date"] = pd.to_datetime(holiday_df["holiday_date"], errors="coerce")
    holiday_df = holiday_df.dropna(subset=["holiday_date"]).copy()

    holiday_df["year"] = holiday_df["holiday_date"].dt.year

    yearly = (
        holiday_df.groupby("year", as_index=False)
        .agg(
            holiday_count=("holiday_date", "nunique"),
            holiday_names=("holiday_name", lambda x: ", ".join(sorted(set(x.astype(str)))))
        )
    )

    return yearly


for path in [
    ROUTE_PATH,
    COMPETITION_PATH,
    COUNTRY_PATH,
    EXCHANGE_PATH,
    HOLIDAY_PATH,
]:
    check_file(path)

route_df = pd.read_csv(ROUTE_PATH, encoding="utf-8-sig")
competition_df = pd.read_csv(COMPETITION_PATH, encoding="utf-8-sig")
country_df = pd.read_csv(COUNTRY_PATH, encoding="utf-8-sig")
exchange_df = pd.read_csv(EXCHANGE_PATH, encoding="utf-8-sig")
holiday_df = pd.read_csv(HOLIDAY_PATH, encoding="utf-8-sig")

# 1. 노선 데이터 기본 정리
route_features = route_df.copy()

# 노선 데이터가 "한국-도쿄" 같은 형태라 ICN 기준 경쟁도 데이터와 직접 route 조인이 어려움.
# 따라서 1차 MVP에서는 연도 기준으로 경쟁도 평균값을 붙임.
competition_yearly = (
    competition_df.groupby("year", as_index=False)
    .agg(
        avg_carrier_count=("carrier_count", "mean"),
        avg_lcc_share=("lcc_share", "mean"),
        avg_icn_total_flight_count=("total_flight_count", "mean"),
        avg_icn_total_paid_passenger_count=("total_paid_passenger_count", "mean"),
        avg_icn_passengers_per_flight=("passengers_per_flight", "mean"),
    )
)

competition_yearly["avg_carrier_count"] = competition_yearly["avg_carrier_count"].round(2)
competition_yearly["avg_lcc_share"] = competition_yearly["avg_lcc_share"].round(4)
competition_yearly["avg_icn_total_flight_count"] = competition_yearly["avg_icn_total_flight_count"].round(2)
competition_yearly["avg_icn_total_paid_passenger_count"] = competition_yearly["avg_icn_total_paid_passenger_count"].round(2)
competition_yearly["avg_icn_passengers_per_flight"] = competition_yearly["avg_icn_passengers_per_flight"].round(2)

# 2. 일본 국가 단위 성장률 붙이기
country_japan = country_df.copy()

country_japan = country_japan.rename(
    columns={
        "passenger_growth_rate": "japan_country_passenger_growth_rate",
        "flight_growth_rate": "japan_country_flight_growth_rate",
        "cargo_growth_rate": "japan_country_cargo_growth_rate",
        "passengers_per_flight": "japan_country_passengers_per_flight",
        "passenger_count": "japan_country_passenger_count",
        "flight_count": "japan_country_flight_count",
        "cargo_ton": "japan_country_cargo_ton",
    }
)

country_cols = [
    "year",
    "japan_country_passenger_count",
    "japan_country_flight_count",
    "japan_country_cargo_ton",
    "japan_country_passenger_growth_rate",
    "japan_country_flight_growth_rate",
    "japan_country_cargo_growth_rate",
    "japan_country_passengers_per_flight",
]

country_japan = country_japan[country_cols].copy()

# 3. 환율 연도별 최신값 붙이기
exchange_yearly = get_latest_exchange_by_year(exchange_df)

# 4. 공휴일 연도별 개수 붙이기
holiday_yearly = get_holiday_count_by_year(holiday_df)

# 5. 연도 기준 통합
feature_df = route_features.merge(
    competition_yearly,
    on="year",
    how="left",
)

feature_df = feature_df.merge(
    country_japan,
    on="year",
    how="left",
)

feature_df = feature_df.merge(
    exchange_yearly,
    on="year",
    how="left",
)

feature_df = feature_df.merge(
    holiday_yearly,
    on="year",
    how="left",
)

# 6. 결측치 처리
numeric_cols = [
    "passenger_growth_rate",
    "flight_growth_rate",
    "cargo_growth_rate",
    "passengers_per_flight",
    "avg_carrier_count",
    "avg_lcc_share",
    "avg_icn_total_flight_count",
    "avg_icn_total_paid_passenger_count",
    "avg_icn_passengers_per_flight",
    "japan_country_passenger_count",
    "japan_country_flight_count",
    "japan_country_cargo_ton",
    "japan_country_passenger_growth_rate",
    "japan_country_flight_growth_rate",
    "japan_country_cargo_growth_rate",
    "japan_country_passengers_per_flight",
    "jpy_krw_rate",
    "jpy_krw_change_rate_7d",
    "jpy_krw_change_rate_30d",
    "jpy_krw_change_rate_90d",
    "holiday_count",
]

for col in numeric_cols:
    if col in feature_df.columns:
        feature_df[col] = feature_df[col].fillna(0)

if "holiday_names" in feature_df.columns:
    feature_df["holiday_names"] = feature_df["holiday_names"].fillna("")

# 7. 위험도 점수용 간단 파생 변수
# 수요 증가율이 높을수록 가격 상승 위험 +
# 공급 증가율이 낮거나 음수일수록 가격 상승 위험 +
# 환율 상승률이 높을수록 일본 여행 비용 부담 +
# 항공사 수가 적을수록 경쟁 약함

feature_df["demand_pressure_score"] = feature_df["passenger_growth_rate"].apply(
    lambda x: 5 if x >= 50 else 4 if x >= 20 else 3 if x >= 5 else 2 if x >= 0 else 1
)

feature_df["supply_pressure_score"] = feature_df["flight_growth_rate"].apply(
    lambda x: 5 if x < 0 else 4 if x < 5 else 3 if x < 15 else 2 if x < 30 else 1
)

feature_df["exchange_pressure_score"] = feature_df["jpy_krw_change_rate_30d"].apply(
    lambda x: 5 if x >= 5 else 4 if x >= 3 else 3 if x >= 1 else 2 if x >= 0 else 1
)

feature_df["competition_pressure_score"] = feature_df["avg_carrier_count"].apply(
    lambda x: 5 if x <= 2 else 4 if x <= 4 else 3 if x <= 6 else 2 if x <= 8 else 1
)

feature_df["holiday_pressure_score"] = feature_df["holiday_count"].apply(
    lambda x: 4 if x >= 15 else 3 if x >= 10 else 2 if x >= 5 else 1
)

feature_df["risk_score"] = (
    feature_df["demand_pressure_score"]
    + feature_df["supply_pressure_score"]
    + feature_df["exchange_pressure_score"]
    + feature_df["competition_pressure_score"]
    + feature_df["holiday_pressure_score"]
)

feature_df["risk_level"] = feature_df["risk_score"].apply(
    lambda x: "높음" if x >= 18 else "중간" if x >= 12 else "낮음"
)

feature_df["purchase_timing_recommendation"] = feature_df["risk_level"].map(
    {
        "높음": "빠른 구매 검토",
        "중간": "가격 모니터링 후 구매",
        "낮음": "대기 가능",
    }
)

# 8. 컬럼 정렬
preferred_cols = [
    "year",
    "route",
    "origin",
    "destination",
    "flight_count",
    "passenger_count",
    "cargo_ton",
    "passengers_per_flight",
    "passenger_growth_rate",
    "flight_growth_rate",
    "cargo_growth_rate",
    "avg_carrier_count",
    "avg_lcc_share",
    "avg_icn_total_flight_count",
    "avg_icn_total_paid_passenger_count",
    "avg_icn_passengers_per_flight",
    "japan_country_passenger_count",
    "japan_country_flight_count",
    "japan_country_passenger_growth_rate",
    "japan_country_flight_growth_rate",
    "jpy_krw_rate",
    "jpy_krw_change_rate_7d",
    "jpy_krw_change_rate_30d",
    "jpy_krw_change_rate_90d",
    "holiday_count",
    "holiday_names",
    "demand_pressure_score",
    "supply_pressure_score",
    "exchange_pressure_score",
    "competition_pressure_score",
    "holiday_pressure_score",
    "risk_score",
    "risk_level",
    "purchase_timing_recommendation",
]

existing_cols = [col for col in preferred_cols if col in feature_df.columns]
other_cols = [col for col in feature_df.columns if col not in existing_cols]

feature_df = feature_df[existing_cols + other_cols]

feature_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print("최종 피처 파일 저장:", OUTPUT_PATH)
print("전체 행 수:", len(feature_df))
print("연도 범위:", feature_df["year"].min(), "~", feature_df["year"].max())
print()
print(feature_df.head(20))