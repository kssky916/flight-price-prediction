from pathlib import Path
import pandas as pd

INPUT_PATH = Path("data/processed/processed_holidays.csv")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

if not INPUT_PATH.exists():
    raise FileNotFoundError("data/processed/processed_holidays.csv 파일이 없습니다.")

df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")

# 컬럼 자동 인식
date_col_candidates = ["locdate", "date", "holiday_date", "base_date"]
name_col_candidates = ["dateName", "holiday_name", "name"]
holiday_col_candidates = ["isHoliday", "is_holiday"]

date_col = next((col for col in date_col_candidates if col in df.columns), None)
name_col = next((col for col in name_col_candidates if col in df.columns), None)
holiday_col = next((col for col in holiday_col_candidates if col in df.columns), None)

if date_col is None:
    raise ValueError(f"날짜 컬럼을 찾지 못했습니다. 현재 컬럼: {list(df.columns)}")

if name_col is None:
    raise ValueError(f"공휴일명 컬럼을 찾지 못했습니다. 현재 컬럼: {list(df.columns)}")

clean_df = df.copy()

clean_df["holiday_date"] = pd.to_datetime(
    clean_df[date_col].astype(str),
    format="%Y%m%d",
    errors="coerce"
)

clean_df["holiday_name"] = clean_df[name_col].astype(str).str.strip()

if holiday_col:
    clean_df["is_holiday"] = clean_df[holiday_col].astype(str)
else:
    clean_df["is_holiday"] = "Y"

clean_df = clean_df[
    clean_df["holiday_date"].notna()
].copy()

clean_df["year"] = clean_df["holiday_date"].dt.year
clean_df["month"] = clean_df["holiday_date"].dt.month
clean_df["day"] = clean_df["holiday_date"].dt.day
clean_df["weekday"] = clean_df["holiday_date"].dt.day_name()

clean_df = clean_df[
    [
        "holiday_date",
        "year",
        "month",
        "day",
        "weekday",
        "holiday_name",
        "is_holiday",
    ]
].copy()

clean_df = clean_df.drop_duplicates(
    subset=["holiday_date", "holiday_name"]
).sort_values("holiday_date")

save_path = PROCESSED_DIR / "processed_holidays_clean.csv"
clean_df.to_csv(save_path, index=False, encoding="utf-8-sig")

print("공휴일 정제 파일 저장:", save_path)
print("전체 행 수:", len(clean_df))
print("연도 범위:", clean_df["year"].min(), "~", clean_df["year"].max())
print()
print(clean_df.head(20))