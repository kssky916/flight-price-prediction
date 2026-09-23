import requests
import pandas as pd
from pathlib import Path
import time

SERVICE_KEY = "d5e0753993c06e7dac44854f0cdd3a12418a1009a3f054f2b505e4a5f7d6d71e"

BASE_URL = "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsDSOdp/getPassengerDeparturesDSOdp"

JAPAN_AIRPORTS = ["NRT", "HND", "KIX", "FUK", "CTS", "OKA", "NGO"]

rows = []

for airport_code in JAPAN_AIRPORTS:
    params = {
        "serviceKey": SERVICE_KEY,
        "airport_code": airport_code,
        "type": "json",
    }

    response = requests.get(BASE_URL, params=params)

    print(f"{airport_code} 상태코드:", response.status_code)
    print(response.text[:300])

    data = response.json()

    if "response" not in data:
        print("에러 응답:", data)
        continue

    body = data["response"].get("body", {})
    items = body.get("items")

    if not items:
        print(f"{airport_code}: 조회 결과 없음")
        continue

    # 이번 API는 items가 바로 list로 내려옴
    if isinstance(items, list):
        item_list = items
    elif isinstance(items, dict):
        item_list = items.get("item", [])
        if isinstance(item_list, dict):
            item_list = [item_list]
    else:
        print(f"{airport_code}: 알 수 없는 items 구조")
        continue

    for row in item_list:
        row["target_airport_code"] = airport_code
        rows.append(row)

    time.sleep(0.2)

df = pd.DataFrame(rows)

if df.empty:
    print("저장할 데이터 없음")
else:
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    save_path = "data/processed/processed_icn_weekly_departures.csv"
    df.to_csv(save_path, index=False, encoding="utf-8-sig")

    print(df.head())
    print("총 행 수:", len(df))
    print("저장 완료:", save_path)