from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agents import run_agent_pipeline
from src.data_loader import find_route_feature, load_sample_route_features
from src.llm_client import parse_travel_request
from src.response_generator import generate_purchase_timing_report
from src.travel_recommender import (
    complete_parsed_request,
    recommend_routes_from_request,
)


app = FastAPI(
    title="Flight Price Risk API",
    description="공공데이터 기반 항공권 가격 상승 위험도 및 구매 타이밍 판단 API",
    version="0.2.0",
)


HOLIDAY_FALLBACK_DATES = {
    2027: {
        "설날": ["2027-02-06", "2027-02-07", "2027-02-08"],
        "추석": ["2027-09-14", "2027-09-15", "2027-09-16"],
        "크리스마스": ["2027-12-25"],
    },
    2026: {
        "설날": ["2026-02-16", "2026-02-17", "2026-02-18"],
        "추석": ["2026-09-24", "2026-09-25", "2026-09-26"],
        "크리스마스": ["2026-12-25"],
    },
}


class RouteAnalyzeRequest(BaseModel):
    departure_airport: str = Field(..., description="출발 공항 코드 또는 이름")
    arrival_airport: str = Field(..., description="도착 공항 코드 또는 이름")
    departure_date: str = Field(..., description="출발일 YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="귀국일 YYYY-MM-DD")
    arrival_date: Optional[str] = Field(None, description="귀국일 YYYY-MM-DD")
    year: Optional[int] = Field(None, description="분석 기준 연도")


class TextRecommendRequest(BaseModel):
    text: str = Field(..., description="사용자 자연어 여행 조건")
    recommendation_count: int = Field(5, description="추천 결과 개수")


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")

    except Exception:
        return None


def _get_holidays_in_range(
    departure_date: Optional[str],
    return_date: Optional[str],
) -> Dict[str, List[str]]:
    start_date = _parse_date(departure_date)
    end_date = _parse_date(return_date)

    if start_date is None:
        return {
            "holiday_names": [],
            "holiday_dates": [],
        }

    if end_date is None:
        end_date = start_date

    if end_date < start_date:
        end_date = start_date

    holiday_names = []
    holiday_dates = []

    target_years = sorted(list(set([start_date.year, end_date.year])))

    for year in target_years:
        holiday_map = HOLIDAY_FALLBACK_DATES.get(year, {})

        for holiday_name, date_values in holiday_map.items():
            for date_value in date_values:
                holiday_date = _parse_date(date_value)

                if holiday_date and start_date <= holiday_date <= end_date:
                    if holiday_name not in holiday_names:
                        holiday_names.append(holiday_name)

                    holiday_dates.append(date_value)

    return {
        "holiday_names": holiday_names,
        "holiday_dates": sorted(list(set(holiday_dates))),
    }


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _to_json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [_to_json_safe(item) for item in value]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)

        if np.isnan(value) or np.isinf(value):
            return None

        return value

    if isinstance(value, float):
        if np.isnan(value) or np.isinf(value):
            return None

        return value

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    try:
        if pd.isna(value):
            return None

    except Exception:
        pass

    return value


def _select_analysis_year(
    df: pd.DataFrame,
    departure_airport: str,
    arrival_airport: str,
    departure_date: Optional[str],
    year: Optional[int],
) -> int:
    route_df = df[
        (df["departure_airport"] == departure_airport)
        & (df["arrival_airport"] == arrival_airport)
    ].copy()

    if route_df.empty:
        return year or int(str(departure_date)[:4])

    available_years = sorted(route_df["year"].dropna().astype(int).unique().tolist())

    if not available_years:
        return year or int(str(departure_date)[:4])

    if year and year in available_years:
        return year

    if departure_date:
        requested_year = int(str(departure_date)[:4])
    elif year:
        requested_year = year
    else:
        requested_year = max(available_years)

    past_years = [
        available_year
        for available_year in available_years
        if available_year <= requested_year
    ]

    if past_years:
        return max(past_years)

    return max(available_years)


def _build_route_sample_input(
    matched_feature: Dict[str, Any],
    request: RouteAnalyzeRequest,
) -> Dict[str, Any]:
    sample_input = dict(matched_feature)

    return_date = request.return_date or request.arrival_date

    sample_input["departure_date"] = request.departure_date

    if return_date:
        sample_input["return_date"] = return_date
        sample_input["arrival_date"] = return_date

    holiday_info = _get_holidays_in_range(
        departure_date=request.departure_date,
        return_date=return_date,
    )

    holiday_dates = holiday_info["holiday_dates"]
    holiday_names = holiday_info["holiday_names"]

    if holiday_dates:
        sample_input["required_include_dates"] = holiday_dates
        sample_input["must_include_dates"] = holiday_dates
        sample_input["must_include_holiday_names"] = holiday_names
        sample_input["holiday_count"] = len(holiday_dates)
        sample_input["holiday_name"] = ", ".join(holiday_names)

    return sample_input


def _safe_ai_report(risk_result: Dict[str, Any]) -> str:
    try:
        return generate_purchase_timing_report(risk_result)

    except Exception as error:
        return (
            "### AI 2차 검토 결과\n\n"
            "AI 검토 결과를 생성하지 못했습니다. "
            f"기본 위험도 산정 결과를 우선 확인하세요. 오류: {error}"
        )


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
            departure_airport=request.departure_airport,
            arrival_airport=request.arrival_airport,
            departure_date=request.departure_date,
            year=request.year,
        )

        matched_feature = find_route_feature(
            df=df,
            departure_airport=request.departure_airport,
            arrival_airport=request.arrival_airport,
            departure_date=request.departure_date,
            year=analysis_year,
        )

        sample_input = _build_route_sample_input(
            matched_feature=matched_feature,
            request=request,
        )

        risk_result = run_agent_pipeline(sample_input)
        ai_report = _safe_ai_report(risk_result)

        response = {
            "status": "success",
            "input": {
                "departure_airport": request.departure_airport,
                "arrival_airport": request.arrival_airport,
                "departure_date": request.departure_date,
                "return_date": request.return_date,
                "arrival_date": request.arrival_date,
                "year": request.year,
            },
            "analysis_year": analysis_year,
            "risk_result": risk_result,
            "matched_feature": matched_feature,
            "ai_report": ai_report,
        }

        return _to_json_safe(response)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@app.post("/recommend/text")
def recommend_by_text(request: TextRecommendRequest):
    try:
        df = load_sample_route_features()

        parsed_request = parse_travel_request(request.text)
        parsed_request["text"] = request.text

        completed_request = complete_parsed_request(parsed_request)

        recommendations = recommend_routes_from_request(
            df=df,
            parsed_request=completed_request,
            recommendation_count=request.recommendation_count,
        )

        top_ai_report = ""

        if recommendations:
            top_ai_report = _safe_ai_report(recommendations[0]["risk_result"])

        response = {
            "status": "success",
            "input": {
                "text": request.text,
                "recommendation_count": request.recommendation_count,
            },
            "parsed_request": parsed_request,
            "completed_request": completed_request,
            "recommendations": recommendations,
            "top_ai_report": top_ai_report,
        }

        return _to_json_safe(response)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )