from typing import Optional, Any

import math
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.data_loader import load_sample_route_features, find_route_feature
from src.agents import run_agent_pipeline
from src.response_generator import generate_purchase_timing_report
from src.llm_client import parse_travel_request
from src.travel_recommender import recommend_routes_from_request, complete_parsed_request


app = FastAPI(
    title="Flight Price Risk API",
    description="공공데이터 기반 항공권 가격 상승 위험도 및 구매 타이밍 판단 API",
    version="0.1.0",
)


class RouteAnalyzeRequest(BaseModel):
    departure_airport: str
    arrival_airport: str
    departure_date: str
    arrival_date: Optional[str] = None
    year: Optional[int] = None


class TextRecommendRequest(BaseModel):
    text: str
    recommendation_count: Optional[int] = 5


def _to_json_safe(value: Any):
    if value is None:
        return None

    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [_to_json_safe(v) for v in value]

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")

    if pd.isna(value):
        return None

    return value


def _select_analysis_year(df, departure_date: str, request_year: Optional[int] = None) -> int:
    if request_year is not None:
        return request_year

    available_years = sorted(df["year"].dropna().astype(int).unique().tolist())
    target_year = int(str(departure_date)[:4])

    if target_year in available_years:
        return target_year

    past_years = [year for year in available_years if year <= target_year]

    if past_years:
        return max(past_years)

    return max(available_years)


def _build_sample_input(matched_feature, departure_airport, arrival_airport, departure_date):
    return {
        **matched_feature,
        "departure_airport": matched_feature.get("departure_airport", departure_airport),
        "arrival_airport": matched_feature.get("arrival_airport", arrival_airport),
        "departure_date": departure_date,
        "passenger_growth_rate": matched_feature.get("passenger_growth_rate", 0),
        "flight_growth_rate": matched_feature.get("flight_growth_rate", 0),
        "days_to_holiday": matched_feature.get("days_to_holiday", 0),
        "holiday_name": matched_feature.get("holiday_name", ""),
        "holiday_count": matched_feature.get("holiday_count", 0),
        "jpy_krw_change_rate": matched_feature.get("jpy_krw_change_rate", 0),
        "delay_rate": matched_feature.get("delay_rate", 0),
        "cancel_count": matched_feature.get("cancel_count", 0),
        "avg_carrier_count": matched_feature.get("avg_carrier_count", 0),
        "avg_lcc_share": matched_feature.get("avg_lcc_share", 0),
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Flight Price Risk API is running",
    }


@app.post("/analyze/route")
def analyze_route(request: RouteAnalyzeRequest):
    try:
        df = load_sample_route_features()

        analysis_year = _select_analysis_year(
            df=df,
            departure_date=request.departure_date,
            request_year=request.year,
        )

        matched_feature = find_route_feature(
            df=df,
            departure_airport=request.departure_airport,
            arrival_airport=request.arrival_airport,
            departure_date=request.departure_date,
            year=analysis_year,
        )

        sample_input = _build_sample_input(
            matched_feature=matched_feature,
            departure_airport=request.departure_airport,
            arrival_airport=request.arrival_airport,
            departure_date=request.departure_date,
        )

        risk_result = run_agent_pipeline(sample_input)
        ai_report = generate_purchase_timing_report(risk_result)

        response = {
            "status": "success",
            "input": request.dict(),
            "analysis_year": analysis_year,
            "risk_result": risk_result,
            "matched_feature": matched_feature,
            "ai_report": ai_report,
        }

        return _to_json_safe(response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend/text")
def recommend_by_text(request: TextRecommendRequest):
    try:
        df = load_sample_route_features()

        parsed_request = parse_travel_request(request.text)
        parsed_request = complete_parsed_request(parsed_request)
        parsed_request["recommendation_count"] = request.recommendation_count

        recommendations = recommend_routes_from_request(
            df=df,
            parsed_request=parsed_request,
        )

        top_ai_report = None

        if recommendations:
            top_ai_report = generate_purchase_timing_report(
                recommendations[0]["risk_result"]
            )

        response = {
            "status": "success",
            "input_text": request.text,
            "parsed_request": parsed_request,
            "recommendations": recommendations,
            "top_ai_report": top_ai_report,
        }

        return _to_json_safe(response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))