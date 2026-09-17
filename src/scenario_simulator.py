from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.agents import run_agent_pipeline


def build_shifted_input(base_input: Dict[str, Any], day_shift: int) -> Dict[str, Any]:
    shifted_input = deepcopy(base_input)

    base_date = datetime.fromisoformat(str(base_input["departure_date"])).date()
    shifted_date = base_date + timedelta(days=day_shift)

    shifted_input["departure_date"] = str(shifted_date)

    base_days_to_holiday = base_input.get("days_to_holiday", 0)
    shifted_input["days_to_holiday"] = max(0, base_days_to_holiday + day_shift)

    base_passenger_growth = base_input.get("passenger_growth_rate", 0)

    if day_shift > 0:
        shifted_input["passenger_growth_rate"] = round(
            max(-20, base_passenger_growth - (day_shift * 1.5)),
            1
        )
    elif day_shift < 0:
        shifted_input["passenger_growth_rate"] = round(
            min(50, base_passenger_growth + (abs(day_shift) * 1.0)),
            1
        )

    if day_shift == 0:
        shifted_input["scenario_name"] = "기준 일정"
    elif day_shift > 0:
        shifted_input["scenario_name"] = f"{day_shift}일 뒤 출발"
    else:
        shifted_input["scenario_name"] = f"{abs(day_shift)}일 앞당김"

    shifted_input["scenario_assumption"] = (
        "현재 What-if 시뮬레이션은 실제 미래 가격 예측이 아니라, "
        "출발일 변경에 따른 연휴 인접도와 수요 집중 완화 가능성을 단순 가정하여 비교합니다."
    )

    return shifted_input


def generate_date_shift_scenarios(
    base_input: Dict[str, Any],
    day_shifts: List[int] = None
) -> List[Dict[str, Any]]:
    if day_shifts is None:
        day_shifts = [0, 3, 7]

    scenario_results = []

    for day_shift in day_shifts:
        scenario_input = build_shifted_input(base_input, day_shift)
        risk_result = run_agent_pipeline(scenario_input)

        scenario_results.append({
            "scenario_name": scenario_input["scenario_name"],
            "departure_date": scenario_input["departure_date"],
            "day_shift": day_shift,
            "risk_level": risk_result["risk_assessment"]["risk_level"],
            "risk_score": risk_result["risk_assessment"]["risk_score"],
            "max_score": risk_result["risk_assessment"]["max_score"],
            "recommendation": risk_result["risk_assessment"]["recommendation"],
            "summary": risk_result["risk_assessment"]["summary"],
            "passenger_growth_rate": scenario_input["passenger_growth_rate"],
            "days_to_holiday": scenario_input["days_to_holiday"],
            "risk_result": risk_result
        })

    return scenario_results