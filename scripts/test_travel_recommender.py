import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from src.data_loader import load_sample_route_features
from src.llm_client import parse_travel_request
from src.travel_recommender import recommend_routes_from_request


text = """
12월20일~12월30일사이 4박5일로 여행갈거야.
근데 크리스마스는 여행기간에 껴있었으면 좋겠어.
일본으로 갈거야
추천해줘
"""

df = load_sample_route_features()
parsed = parse_travel_request(text)
recommendations = recommend_routes_from_request(df, parsed)

print("추출 조건:")
print(parsed)

print("\n추천 결과:")
for idx, item in enumerate(recommendations, start=1):
    print(
        idx,
        item["departure_airport"],
        "→",
        item["arrival_airport"],
        item["departure_date"],
        "~",
        item["return_date"],
        item["risk_level"],
        item["risk_score"],
        item["purchase_timing_recommendation"],
        "필수포함:",
        item.get("required_include_dates"),
    )