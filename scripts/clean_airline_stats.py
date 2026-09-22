from pathlib import Path
import re
import pandas as pd

RAW_DIR = Path("data/raw/airline_stats")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

LCC_KEYWORDS = [
    "제주항공", "진에어", "티웨이", "에어부산", "에어서울", "이스타",
    "에어로케이", "에어프레미아", "Peach", "피치", "Jetstar", "젯스타",
    "ZIPAIR", "집에어", "Spring", "춘추"
]


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


def is_lcc(airline_name: str) -> bool:
    text = str(airline_name)
    return any(keyword in text for keyword in LCC_KEYWORDS)


all_dfs = []

files = sorted(RAW_DIR.glob("*.xlsx"))

if not files:
    raise FileNotFoundError("data/raw/airline_stats 폴더에 xlsx 파일이 없습니다.")

for file_path in files:
    print("처리 중:", file_path.name)

    year = extract_year(file_path.name)
    df = pd.read_excel(file_path)

    required_cols = ["항공사명", "공급(석)", "운항(편)", "여객(명)", "화물(톤)"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"{file_path.name} 누락 컬럼: {missing_cols}")

    df = df[required_cols].copy()

    df = df.rename(
        columns={
            "항공사명": "airline_name",
            "공급(석)": "seat_supply",
            "운항(편)": "flight_count",
            "여객(명)": "passenger_count",
            "화물(톤)": "cargo_ton",
        }
    )

    df["year"] = year

    df["airline_name"] = df["airline_name"].astype(str).str.strip()

    df["seat_supply"] = df["seat_supply"].apply(clean_number)
    df["flight_count"] = df["flight_count"].apply(clean_number)
    df["passenger_count"] = df["passenger_count"].apply(clean_number)
    df["cargo_ton"] = df["cargo_ton"].apply(clean_number)

    all_dfs.append(df)

airline_df = pd.concat(all_dfs, ignore_index=True)

airline_df = (
    airline_df.groupby(["year", "airline_name"], as_index=False)
    .agg(
        seat_supply=("seat_supply", "sum"),
        flight_count=("flight_count", "sum"),
        passenger_count=("passenger_count", "sum"),
        cargo_ton=("cargo_ton", "sum"),
    )
)

airline_df = airline_df.sort_values(["airline_name", "year"]).reset_index(drop=True)

airline_df["load_factor_proxy"] = airline_df.apply(
    lambda row: row["passenger_count"] / row["seat_supply"]
    if row["seat_supply"] > 0
    else 0,
    axis=1,
)

airline_df["passengers_per_flight"] = airline_df.apply(
    lambda row: row["passenger_count"] / row["flight_count"]
    if row["flight_count"] > 0
    else 0,
    axis=1,
)

airline_df["passenger_growth_rate"] = (
    airline_df.groupby("airline_name")["passenger_count"].pct_change() * 100
)

airline_df["flight_growth_rate"] = (
    airline_df.groupby("airline_name")["flight_count"].pct_change() * 100
)

airline_df["seat_supply_growth_rate"] = (
    airline_df.groupby("airline_name")["seat_supply"].pct_change() * 100
)

airline_df["is_lcc"] = airline_df["airline_name"].apply(is_lcc)

airline_df["load_factor_proxy"] = airline_df["load_factor_proxy"].round(4)
airline_df["passengers_per_flight"] = airline_df["passengers_per_flight"].round(2)
airline_df["passenger_growth_rate"] = airline_df["passenger_growth_rate"].round(2)
airline_df["flight_growth_rate"] = airline_df["flight_growth_rate"].round(2)
airline_df["seat_supply_growth_rate"] = airline_df["seat_supply_growth_rate"].round(2)

save_path = PROCESSED_DIR / "processed_airline_stats.csv"
airline_df.to_csv(save_path, index=False, encoding="utf-8-sig")

print("항공사 데이터 저장:", save_path)
print()
print("전체 행 수:", len(airline_df))
print("연도 범위:", airline_df["year"].min(), "~", airline_df["year"].max())
print()
print(airline_df.head(20))