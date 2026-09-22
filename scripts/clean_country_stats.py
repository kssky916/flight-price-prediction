from pathlib import Path
import re
import pandas as pd

RAW_DIR = Path("data/raw/country_stats")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def extract_year(file_name: str) -> int:
    match = re.search(r"(\d{2})_", file_name)
    if not match:
        raise ValueError(f"파일명에서 연도 추출 실패: {file_name}")

    return 2000 + int(match.group(1))


def clean_number(value):
    if pd.isna(value):
        return 0.0

    value = str(value).replace(",", "").replace("-", "0").strip()

    if value == "" or value.lower() == "nan":
        return 0.0

    return float(value)


all_dfs = []

files = sorted(RAW_DIR.glob("*.xlsx"))

if not files:
    raise FileNotFoundError("data/raw/country_stats 폴더에 xlsx 파일이 없습니다.")

for file_path in files:
    print("처리 중:", file_path.name)

    year = extract_year(file_path.name)
    df = pd.read_excel(file_path)

    required_cols = ["지역", "국가", "운항(편)", "여객(명)", "화물(톤)"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"{file_path.name} 누락 컬럼: {missing_cols}")

    df = df[required_cols].copy()

    df = df.rename(
        columns={
            "지역": "region",
            "국가": "country",
            "운항(편)": "flight_count",
            "여객(명)": "passenger_count",
            "화물(톤)": "cargo_ton",
        }
    )

    df["year"] = year

    df["region"] = df["region"].astype(str).str.strip()
    df["country"] = df["country"].astype(str).str.strip()

    df["flight_count"] = df["flight_count"].apply(clean_number)
    df["passenger_count"] = df["passenger_count"].apply(clean_number)
    df["cargo_ton"] = df["cargo_ton"].apply(clean_number)

    all_dfs.append(df)

country_df = pd.concat(all_dfs, ignore_index=True)

country_df = (
    country_df.groupby(["year", "region", "country"], as_index=False)
    .agg(
        flight_count=("flight_count", "sum"),
        passenger_count=("passenger_count", "sum"),
        cargo_ton=("cargo_ton", "sum"),
    )
)

country_df = country_df.sort_values(["country", "year"]).reset_index(drop=True)

country_df["passenger_growth_rate"] = (
    country_df.groupby("country")["passenger_count"].pct_change() * 100
)

country_df["flight_growth_rate"] = (
    country_df.groupby("country")["flight_count"].pct_change() * 100
)

country_df["cargo_growth_rate"] = (
    country_df.groupby("country")["cargo_ton"].pct_change() * 100
)

country_df["passengers_per_flight"] = country_df.apply(
    lambda row: row["passenger_count"] / row["flight_count"]
    if row["flight_count"] > 0
    else 0,
    axis=1,
)

country_df["passenger_growth_rate"] = country_df["passenger_growth_rate"].round(2)
country_df["flight_growth_rate"] = country_df["flight_growth_rate"].round(2)
country_df["cargo_growth_rate"] = country_df["cargo_growth_rate"].round(2)
country_df["passengers_per_flight"] = country_df["passengers_per_flight"].round(2)

japan_df = country_df[
    country_df["country"].astype(str).str.contains("일본|JAPAN|Japan", na=False)
].copy()

country_save_path = PROCESSED_DIR / "processed_country_stats.csv"
japan_save_path = PROCESSED_DIR / "processed_country_stats_japan.csv"

country_df.to_csv(country_save_path, index=False, encoding="utf-8-sig")
japan_df.to_csv(japan_save_path, index=False, encoding="utf-8-sig")

print("전체 국가 데이터 저장:", country_save_path)
print("일본 국가 데이터 저장:", japan_save_path)
print()
print("전체 행 수:", len(country_df))
print("일본 행 수:", len(japan_df))
print("연도 범위:", country_df["year"].min(), "~", country_df["year"].max())
print()
print(japan_df)