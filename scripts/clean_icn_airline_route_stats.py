from pathlib import Path
import re
import pandas as pd

RAW_DIR = Path("data/raw/icn_airline_route_stats")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

USE_FILE_KEYWORDS = [
    "20221231",
    "20231231",
    "20241231",
    "20251231",
    "20260707",
]

JAPAN_AIRPORT_CODES = [
    "NRT", "HND", "KIX", "FUK", "CTS", "OKA", "NGO", "KMJ", "UKB",
    "HIJ", "MYJ", "KOJ", "OIT", "KMI", "TAK", "SDJ", "AOJ", "FSZ",
    "KIJ", "OKJ", "YGJ", "KKJ", "ISG", "NGS"
]

JAPAN_KEYWORDS = [
    "일본", "나리타", "하네다", "간사이", "오사카", "후쿠오카", "삿포로",
    "오키나와", "나고야", "구마모토", "구마모도", "고베", "히로시마",
    "마쓰야마", "가고시마", "미야자키", "오이타", "다카마쓰", "센다이",
]

LCC_KEYWORDS = [
    "제주항공", "진에어", "티웨이", "에어부산", "에어서울", "이스타",
    "Peach", "피치", "Jetstar", "젯스타", "Spring", "춘추", "ZIPAIR", "집에어",
    "에어로케이", "Aero K", "에어프레미아", "Air Premia"
]


def read_csv_auto(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]

    for encoding in encodings:
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"CSV 인코딩 실패: {path.name}")


def clean_number(value):
    if pd.isna(value):
        return 0.0

    value = str(value).replace(",", "").replace("-", "0").strip()

    if value == "" or value.lower() == "nan":
        return 0.0

    return float(value)


def extract_year_from_filename(file_name: str) -> int:
    match = re.search(r"20(\d{2})", file_name)
    if not match:
        raise ValueError(f"파일명에서 연도 추출 실패: {file_name}")

    return 2000 + int(match.group(1))


def normalize_year(value, default_year):
    if pd.isna(value):
        return default_year

    value = str(value).strip()
    value = value.replace("년", "")
    value = value.replace(" ", "")

    if value == "" or value.lower() == "nan":
        return default_year

    return int(float(value))


def normalize_month(value):
    if pd.isna(value):
        return None

    value = str(value).strip()
    value = value.replace("월", "")
    value = value.replace(" ", "")

    if value == "" or value.lower() == "nan":
        return None

    return int(float(value))


def split_year_month_from_yyyymm(value):
    value = str(value).replace("-", "").replace(".", "").replace(" ", "").strip()

    if len(value) < 6:
        return None, None

    year = int(value[:4])
    month = int(value[4:6])

    return year, month


def is_lcc(airline_name: str) -> bool:
    text = str(airline_name)
    return any(keyword in text for keyword in LCC_KEYWORDS)


def is_japan(row) -> bool:
    airport_code = str(row.get("airport_code", "")).strip()

    text = " ".join(
        [
            str(row.get("country", "")),
            airport_code,
            str(row.get("route_name", "")),
            str(row.get("airport_name", "")),
        ]
    )

    if airport_code in JAPAN_AIRPORT_CODES:
        return True

    return any(keyword in text for keyword in JAPAN_KEYWORDS)


all_dfs = []

files = sorted(RAW_DIR.glob("*.csv"))

if not files:
    raise FileNotFoundError("data/raw/icn_airline_route_stats 폴더에 csv 파일이 없습니다.")

target_files = [
    file_path for file_path in files
    if any(keyword in file_path.name for keyword in USE_FILE_KEYWORDS)
]

if not target_files:
    raise FileNotFoundError("사용 대상 파일을 찾지 못했습니다. 파일명을 확인하세요.")

for file_path in target_files:
    print("처리 중:", file_path.name)

    raw = read_csv_auto(file_path)
    year_from_file = extract_year_from_filename(file_path.name)

    df = raw.copy()

    # 2022~2024 구조: 년월 컬럼
    if "년월" in df.columns:
        df[["year", "month"]] = df["년월"].apply(
            lambda x: pd.Series(split_year_month_from_yyyymm(x))
        )
    else:
        if "년도" in df.columns:
            df["year"] = df["년도"].apply(lambda x: normalize_year(x, year_from_file))
        else:
            df["year"] = year_from_file

        if "월" in df.columns:
            df["month"] = df["월"].apply(normalize_month)
        else:
            df["month"] = 0

    rename_map = {}

    if "항공사(IATA)" in df.columns:
        rename_map["항공사(IATA)"] = "airline_iata"

    if "항공사명" in df.columns:
        rename_map["항공사명"] = "airline_name"

    if "국가" in df.columns:
        rename_map["국가"] = "country"

    if "공항" in df.columns:
        rename_map["공항"] = "airport_name"

    if "경유지공항" in df.columns:
        rename_map["경유지공항"] = "airport_code"

    if "노선" in df.columns:
        rename_map["노선"] = "route_name"

    if "여객_화물" in df.columns:
        rename_map["여객_화물"] = "passenger_cargo_type"

    if "국제_국내" in df.columns:
        rename_map["국제_국내"] = "international_domestic"

    if "도착_출발" in df.columns:
        rename_map["도착_출발"] = "arrival_departure"

    if "운항(편)" in df.columns:
        rename_map["운항(편)"] = "flight_count"

    if "유임승객(명)" in df.columns:
        rename_map["유임승객(명)"] = "paid_passenger_count"

    df = df.rename(columns=rename_map)

    for col in [
        "airline_iata",
        "airline_name",
        "country",
        "airport_name",
        "airport_code",
        "route_name",
        "passenger_cargo_type",
        "international_domestic",
        "arrival_departure",
    ]:
        if col not in df.columns:
            df[col] = ""

    if "flight_count" not in df.columns:
        df["flight_count"] = 0

    if "paid_passenger_count" not in df.columns:
        df["paid_passenger_count"] = 0

    df["flight_count"] = df["flight_count"].apply(clean_number)
    df["paid_passenger_count"] = df["paid_passenger_count"].apply(clean_number)

    df["year"] = df["year"].apply(lambda x: normalize_year(x, year_from_file))
    df["month"] = df["month"].apply(normalize_month).fillna(0).astype(int)

    df["airport_code"] = df["airport_code"].astype(str).str.strip()
    df["airline_name"] = df["airline_name"].astype(str).str.strip()
    df["airline_iata"] = df["airline_iata"].astype(str).str.strip()
    df["country"] = df["country"].astype(str).str.strip()
    df["airport_name"] = df["airport_name"].astype(str).str.strip()
    df["route_name"] = df["route_name"].astype(str).str.strip()

    # 국제선만 사용
    df = df[
        (df["international_domestic"] == "")
        | (df["international_domestic"].astype(str).str.contains("국제", na=False))
    ].copy()

    # 여객 데이터만 사용
    df = df[
        (df["passenger_cargo_type"] == "")
        | (df["passenger_cargo_type"].astype(str).str.contains("여객", na=False))
    ].copy()

    df["origin_airport"] = "ICN"
    df["destination_airport"] = df["airport_code"]
    df["route"] = "ICN-" + df["destination_airport"]

    df["is_lcc"] = df["airline_name"].apply(is_lcc)
    df["is_japan_route"] = df.apply(is_japan, axis=1)
    df["source_file"] = file_path.name

    keep_cols = [
        "year",
        "month",
        "origin_airport",
        "destination_airport",
        "route",
        "country",
        "airport_name",
        "route_name",
        "airline_iata",
        "airline_name",
        "arrival_departure",
        "flight_count",
        "paid_passenger_count",
        "is_lcc",
        "is_japan_route",
        "source_file",
    ]

    all_dfs.append(df[keep_cols])

clean_df = pd.concat(all_dfs, ignore_index=True)

clean_df = clean_df[
    (clean_df["destination_airport"] != "")
    & (clean_df["destination_airport"] != "nan")
].copy()

clean_df = clean_df.sort_values(
    ["year", "month", "route", "airline_name"]
).reset_index(drop=True)

japan_df = clean_df[clean_df["is_japan_route"]].copy()

competition_df = (
    japan_df.groupby(["year", "month", "route", "destination_airport"], as_index=False)
    .agg(
        total_flight_count=("flight_count", "sum"),
        total_paid_passenger_count=("paid_passenger_count", "sum"),
        carrier_count=("airline_name", "nunique"),
        lcc_carrier_count=("is_lcc", "sum"),
    )
)

competition_df["lcc_share"] = competition_df.apply(
    lambda row: row["lcc_carrier_count"] / row["carrier_count"]
    if row["carrier_count"] > 0
    else 0,
    axis=1,
)

competition_df["passengers_per_flight"] = competition_df.apply(
    lambda row: row["total_paid_passenger_count"] / row["total_flight_count"]
    if row["total_flight_count"] > 0
    else 0,
    axis=1,
)

competition_df["lcc_share"] = competition_df["lcc_share"].round(4)
competition_df["passengers_per_flight"] = competition_df["passengers_per_flight"].round(2)

clean_save_path = PROCESSED_DIR / "processed_icn_airline_route_stats.csv"
japan_save_path = PROCESSED_DIR / "processed_icn_airline_route_stats_japan.csv"
competition_save_path = PROCESSED_DIR / "processed_icn_route_competition_japan.csv"

clean_df.to_csv(clean_save_path, index=False, encoding="utf-8-sig")
japan_df.to_csv(japan_save_path, index=False, encoding="utf-8-sig")
competition_df.to_csv(competition_save_path, index=False, encoding="utf-8-sig")

print("전체 정제 파일 저장:", clean_save_path)
print("일본 노선 정제 파일 저장:", japan_save_path)
print("일본 노선 경쟁도 파일 저장:", competition_save_path)
print()
print("전체 행 수:", len(clean_df))
print("일본 노선 행 수:", len(japan_df))
print("경쟁도 행 수:", len(competition_df))
print("연도 범위:", clean_df["year"].min(), "~", clean_df["year"].max())
print()
print(competition_df.head(20))