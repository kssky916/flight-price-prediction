import os
from typing import Dict, Any, Optional

import requests


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE_URL}{endpoint}"

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "FastAPI 서버에 연결할 수 없습니다. 먼저 `uvicorn api.main:app --reload`를 실행해주세요."
        )

    except requests.exceptions.Timeout:
        raise RuntimeError("FastAPI 응답 시간이 초과되었습니다.")

    except requests.exceptions.HTTPError as e:
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = response.text

        raise RuntimeError(f"FastAPI 요청 실패: {detail}") from e


def check_api_health() -> Dict[str, Any]:
    url = f"{API_BASE_URL}/health"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "FastAPI 서버에 연결할 수 없습니다. 먼저 `uvicorn api.main:app --reload`를 실행해주세요."
        )


def analyze_route_via_api(
    departure_airport: str,
    arrival_airport: str,
    departure_date: str,
    arrival_date: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    payload = {
        "departure_airport": departure_airport,
        "arrival_airport": arrival_airport,
        "departure_date": departure_date,
        "arrival_date": arrival_date,
        "year": year,
    }

    return _post("/analyze/route", payload)


def recommend_text_via_api(
    text: str,
    recommendation_count: int = 5,
) -> Dict[str, Any]:
    payload = {
        "text": text,
        "recommendation_count": recommendation_count,
    }

    return _post("/recommend/text", payload)
