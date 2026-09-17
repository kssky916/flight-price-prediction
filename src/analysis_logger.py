import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pandas as pd


LOG_PATH = Path("outputs/analysis_logs.csv")


def save_analysis_log(
    risk_result: Dict[str, Any],
    llm_used: bool,
    llm_success: bool,
    query_parse_result: Dict[str, Any] | None = None,
    error_message: str | None = None
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    user_query = risk_result["user_query"]
    risk = risk_result["risk_assessment"]

    log_row = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "departure_airport": user_query["departure_airport"],
        "arrival_airport": user_query["arrival_airport"],
        "route_name": user_query["route_name"],
        "departure_date": user_query["departure_date"],
        "risk_score": risk["risk_score"],
        "max_score": risk["max_score"],
        "risk_level": risk["risk_level"],
        "recommendation": risk["recommendation"],
        "confidence": risk["confidence"],
        "llm_used": llm_used,
        "llm_success": llm_success,
        "query_parser_used": bool(query_parse_result),
        "query_parse_success": query_parse_result.get("parse_success") if query_parse_result else None,
        "error_message": error_message,
        "result_json": json.dumps(risk_result, ensure_ascii=False),
    }

    new_log_df = pd.DataFrame([log_row])

    if LOG_PATH.exists():
        old_log_df = pd.read_csv(LOG_PATH)
        result_df = pd.concat([old_log_df, new_log_df], ignore_index=True)
    else:
        result_df = new_log_df

    result_df.to_csv(LOG_PATH, index=False, encoding="utf-8-sig")