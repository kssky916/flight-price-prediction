import requests
import pandas as pd
from pathlib import Path
import time

SERVICE_KEY = "d5e0753993c06e7dac44854f0cdd3a12418a1009a3f054f2b505e4a5f7d6d71e"

url = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"

rows = []

for year in range(2022, 2027):      # 2022~2026년
    for month in range(1, 13):      # 1~12월
        params = {
            "solYear": str(year),
            "solMonth": f"{month:02d}",
            "ServiceKey": SERVICE_KEY,
            "_type": "json",
            "numOfRows": 100,
        }

        response = requests.get(url, params=params)
        print(f"{year}-{month:02d} 상태코드:", response.status_code)

        data = response.json()

        if "response" not in data:
            print("에러 응답:", data)
            continue

        body = data["response"]["body"]
        items = body.get("items")

        if not items:
            continue

        item = items.get("item")

        if isinstance(item, dict):
            item = [item]

        rows.extend(item)

        time.sleep(0.2)

df = pd.DataFrame(rows)

if df.empty:
    print("가져온 공휴일 데이터가 없습니다.")
else:
    df = df[["locdate", "dateName", "isHoliday", "dateKind", "seq"]]
    df["locdate"] = pd.to_datetime(df["locdate"].astype(str), format="%Y%m%d")
    df = df.sort_values("locdate")

    Path("data/processed").mkdir(parents=True, exist_ok=True)

    save_path = "data/processed/processed_holidays.csv"
    df.to_csv(save_path, index=False, encoding="utf-8-sig")

    print(df)
    print("저장 완료:", save_path)