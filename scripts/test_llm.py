import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents import run_agent_pipeline
from src.llm_client import generate_llm_report


sample_input = {
    "original_text": "9월 말에 인천에서 도쿄 가려고 하는데 지금 사는 게 나을까?",
    "departure_airport": "ICN",
    "arrival_airport": "NRT",
    "route_name": "인천-도쿄",
    "departure_date": "2026-09-25",

    "passenger_growth_rate": 12.5,
    "flight_growth_rate": 2.1,
    "days_to_holiday": 2,
    "holiday_name": "추석 연휴",
    "jpy_krw_change_rate": 3.4,
    "delay_rate": 4.2,
    "cancel_count": 0
}


if __name__ == "__main__":
    risk_result = run_agent_pipeline(sample_input)
    llm_report = generate_llm_report(risk_result)

    print(llm_report)