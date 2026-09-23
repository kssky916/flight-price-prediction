from pathlib import Path
import re
import pandas as pd

RAW_DIR = Path("data/raw/route_stats")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

JAPAN_KEYWORDS = [
    "일본", "도쿄", "나리타", "하네다", "오사카", "간사이", "후쿠오카",
    "삿포로", "오키나와", "나고야", "구마모토", "구마모도", "고베",
    "히로시마", "마쓰야마", "미야자키", "가고시마", "오이타",
    "요나고", "시즈오카", "센다이", "아오모리", "다카마쓰",
    "NRT", "HND", "KIX", "FUK", "CTS", "OKA", "NGO", "KMJ", "UKB"
]


def extract_year(file_name: str) -> int:
    match = re.search(r"(\d{2})_", file_name)
    if not match:
        raise ValueError(f"파일명에서 연도 추출 실패: {file_name}")

    yy = int(match.group(1))
    return 2000 + yy


def clean_number(value):
    if pd.isna(value):
        return 0

    value = str(value).replace(",", "").replace("-", "0").strip()

    if value == "":
        return 0

    return float(value)


def is_japan_route(row) -> bool:
    text = f"{row['origin']} {row['destination']} {row['route']}"
    return any(keyword in text for keyword in JAPAN_KEYWORDS)


all_dfs = []

files = sorted(RAW_DIR.glob("*.xlsx"))

if not files:
    raise FileNotFoundError("data/raw/route_stats 폴더에 xlsx 파일이 없습니다.")

for file_path in files:
    year = extract_year(file_path.name)

    df = pd.read_excel(file_path)

    required_cols = ["노선1", "노선2", "운항(편)", "여객(명)", "화물(톤)"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"{file_path.name} 누락 컬럼: {missing_cols}")

    df = df[required_cols].copy()

    df = df.rename(
        columns={
            "노선1": "origin",
            "노선2": "destination",
            "운항(편)": "flight_count",
            "여객(명)": "passenger_count",
            "화물(톤)": "cargo_ton",
        }
    )

    df["year"] = year

    df["origin"] = df["origin"].astype(str).str.strip()
    df["destination"] = df["destination"].astype(str).str.strip()

    df["flight_count"] = df["flight_count"].apply(clean_number)
    df["passenger_count"] = df["passenger_count"].apply(clean_number)
    df["cargo_ton"] = df["cargo_ton"].apply(clean_number)

    df = df[
        (df["origin"] != "")
        & (df["destination"] != "")
        & (df["origin"] != "nan")
        & (df["destination"] != "nan")
    ].copy()

    df["route"] = df["origin"] + "-" + df["destination"]

    all_dfs.append(df)

route_df = pd.concat(all_dfs, ignore_index=True)

route_df = (
    route_df.groupby(["year", "origin", "destination", "route"], as_index=False)
    .agg(
        flight_count=("flight_count", "sum"),
        passenger_count=("passenger_count", "sum"),
        cargo_ton=("cargo_ton", "sum"),
    )
)

route_df["passengers_per_flight"] = route_df.apply(
    lambda row: row["passenger_count"] / row["flight_count"]
    if row["flight_count"] > 0
    else 0,
    axis=1,
)

route_df = route_df.sort_values(["route", "year"]).reset_index(drop=True)

route_df["passenger_growth_rate"] = (
    route_df.groupby("route")["passenger_count"].pct_change() * 100
)

route_df["flight_growth_rate"] = (
    route_df.groupby("route")["flight_count"].pct_change() * 100
)

route_df["cargo_growth_rate"] = (
    route_df.groupby("route")["cargo_ton"].pct_change() * 100
)

route_df["passenger_growth_rate"] = route_df["passenger_growth_rate"].round(2)
route_df["flight_growth_rate"] = route_df["flight_growth_rate"].round(2)
route_df["cargo_growth_rate"] = route_df["cargo_growth_rate"].round(2)
route_df["passengers_per_flight"] = route_df["passengers_per_flight"].round(2)

route_df["is_japan_route"] = route_df.apply(is_japan_route, axis=1)

japan_route_df = route_df[route_df["is_japan_route"]].copy()

route_save_path = PROCESSED_DIR / "processed_route_stats.csv"
japan_save_path = PROCESSED_DIR / "processed_route_stats_japan.csv"

route_df.to_csv(route_save_path, index=False, encoding="utf-8-sig")
japan_route_df.to_csv(japan_save_path, index=False, encoding="utf-8-sig")

print("전체 노선 데이터 저장:", route_save_path)
print("일본 노선 데이터 저장:", japan_save_path)
print("전체 행 수:", len(route_df))
print("일본 노선 행 수:", len(japan_route_df))
print("연도 범위:", route_df["year"].min(), "~", route_df["year"].max())
print()
print(japan_route_df.head(20))