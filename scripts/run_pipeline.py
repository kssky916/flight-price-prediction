import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents import run_agent_pipeline
from src.response_generator import generate_user_response


sample_input = {
    "original_text": "9월 말에 인천에서 도쿄 가려고 하는데 지금 사는 게 나을까?",
    "departure_airport": "ICN",
    "arrival_airport": "NRT",
    "route_name": "인천-도쿄",
    "departure_date": "2026-09-25",

    # 데이터분석 파트 결과값으로 나중에 교체될 변수
    "passenger_growth_rate": 12.5,
    "flight_growth_rate": 2.1,
    "days_to_holiday": 2,
    "holiday_name": "추석 연휴",
    "jpy_krw_change_rate": 3.4,
    "delay_rate": 4.2,
    "cancel_count": 0
}


def save_outputs(risk_result, result_text):
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "risk_result.json")
    md_path = os.path.join(output_dir, "purchase_timing_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(risk_result, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result_text)

    print(f"JSON 저장 완료: {json_path}")
    print(f"Markdown 리포트 저장 완료: {md_path}")


if __name__ == "__main__":
    risk_result = run_agent_pipeline(sample_input)

    result_text = generate_user_response(risk_result)

    print(result_text)

    save_outputs(risk_result, result_text)