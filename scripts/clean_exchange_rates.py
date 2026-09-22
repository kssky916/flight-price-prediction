from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw/exchange_rates")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TARGET_CURRENCY_CODES = ["JPY"]


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
        return None

    value = str(value).replace(",", "").strip()

    if value == "" or value.lower() == "nan":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def parse_date(value):
    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()
    value = value.replace("-", "")
    value = value.replace(".", "")
    value = value.replace("/", "")

    return pd.to_datetime(value, errors="coerce")


all_dfs = []

files = sorted(RAW_DIR.glob("*.csv"))

if not files:
    raise FileNotFoundError("data/raw/exchange_rates 폴더에 csv 파일이 없습니다.")

for file_path in files:
    print("처리 중:", file_path.name)

    df = read_csv_auto(file_path)
    df.columns = [str(col).strip() for col in df.columns]

    # 재정경제부 파일은 USD/CNY만 있어서 일본 엔화 분석에는 제외
    if file_path.name.startswith("재정경제부"):
        print("제외: JPY 컬럼 없음:", file_path.name)
        continue

    # 한국무역보험공사 파일 구조
    required_cols = ["통화코드", "기준일자", "매매기준율"]

    if not all(col in df.columns for col in required_cols):
        print("사용 불가 파일 - 컬럼 확인 필요:", file_path.name)
        print("현재 컬럼:", list(df.columns))
        continue

    temp = df[required_cols].copy()

    temp = temp.rename(
        columns={
            "통화코드": "currency_code",
            "기준일자": "base_date",
            "매매기준율": "jpy_krw_rate",
        }
    )

    temp["source_file"] = file_path.name

    temp["currency_code"] = temp["currency_code"].astype(str).str.strip()
    temp["jpy_krw_rate"] = temp["jpy_krw_rate"].apply(clean_number)
    temp["base_date"] = temp["base_date"].apply(parse_date)

    temp = temp[
        temp["currency_code"].isin(TARGET_CURRENCY_CODES)
    ].copy()

    temp = temp[
        temp["base_date"].notna()
        & temp["jpy_krw_rate"].notna()
    ].copy()

    if temp.empty:
        print("JPY 데이터 없음:", file_path.name)
        continue

    all_dfs.append(temp)

if not all_dfs:
    raise ValueError("JPY 환율 데이터를 만들 수 없습니다. 한국무역보험공사 파일의 통화코드에 JPY가 있는지 확인하세요.")

exchange_df = pd.concat(all_dfs, ignore_index=True)

exchange_df = exchange_df.drop_duplicates(subset=["base_date"]).copy()
exchange_df = exchange_df.sort_values("base_date").reset_index(drop=True)

exchange_df["year"] = exchange_df["base_date"].dt.year
exchange_df["month"] = exchange_df["base_date"].dt.month
exchange_df["day"] = exchange_df["base_date"].dt.day

exchange_df["jpy_krw_change_rate_7d"] = (
    exchange_df["jpy_krw_rate"].pct_change(periods=7) * 100
)

exchange_df["jpy_krw_change_rate_30d"] = (
    exchange_df["jpy_krw_rate"].pct_change(periods=30) * 100
)

exchange_df["jpy_krw_change_rate_90d"] = (
    exchange_df["jpy_krw_rate"].pct_change(periods=90) * 100
)

exchange_df["jpy_krw_change_rate_7d"] = exchange_df["jpy_krw_change_rate_7d"].round(2)
exchange_df["jpy_krw_change_rate_30d"] = exchange_df["jpy_krw_change_rate_30d"].round(2)
exchange_df["jpy_krw_change_rate_90d"] = exchange_df["jpy_krw_change_rate_90d"].round(2)

save_cols = [
    "base_date",
    "year",
    "month",
    "day",
    "currency_code",
    "jpy_krw_rate",
    "jpy_krw_change_rate_7d",
    "jpy_krw_change_rate_30d",
    "jpy_krw_change_rate_90d",
    "source_file",
]

exchange_df = exchange_df[save_cols]

save_path = PROCESSED_DIR / "processed_exchange_rates_daily.csv"
exchange_df.to_csv(save_path, index=False, encoding="utf-8-sig")

print("환율 정제 파일 저장:", save_path)
print("전체 행 수:", len(exchange_df))
print("기간:", exchange_df["base_date"].min(), "~", exchange_df["base_date"].max())
print()
print(exchange_df.head(20))
print()
print(exchange_df.tail(20))