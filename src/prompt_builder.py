import json
from datetime import datetime
from typing import Dict, Any, List


# =========================
# 1. 분석 결과 샘플 데이터
# =========================

risk_result: Dict[str, Any] = {
    "service": {
        "name": "LLM 기반 항공권 구매 타이밍 의사결정 지원 서비스",
        "analysis_version": "v0.1.0",
        "data_basis": "공공데이터 기반 위험도 산정 결과",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    },

    "user_query": {
        "original_text": "9월 말에 인천에서 도쿄 가려고 하는데 지금 사는 게 나을까?",
        "departure_airport": "ICN",
        "arrival_airport": "NRT",
        "route_name": "인천-도쿄",
        "departure_date": "2026-09-25"
    },

    "risk_assessment": {
        "risk_score": 7,
        "risk_level": "높음",
        "recommendation": "빠른 구매 검토",
        "confidence": "중간",
        "summary": "연휴 인접, 일본행 수요 증가, 공급 증가 제한 요인이 함께 확인되어 가격 상승 위험도가 높게 산정됨"
    },

    "factor_analysis": {
        "demand": {
            "factor_name": "수요",
            "status": "위험",
            "score": 2,
            "evidence": "일본행 여객 수요가 최근 증가했습니다.",
            "business_interpretation": "수요가 증가하면 동일 공급 조건에서 항공권 가격 상승 압력이 커질 수 있습니다."
        },
        "supply": {
            "factor_name": "공급",
            "status": "주의",
            "score": 2,
            "evidence": "운항편 수 증가율이 여객 증가율보다 낮습니다.",
            "business_interpretation": "수요 증가 대비 공급 확대가 제한적이면 좌석 확보 경쟁이 커질 수 있습니다."
        },
        "holiday": {
            "factor_name": "연휴/시기",
            "status": "위험",
            "score": 2,
            "evidence": "출발일이 연휴와 가까운 시점입니다.",
            "business_interpretation": "연휴 인접 시점에는 단기 여행 수요가 집중될 가능성이 있습니다."
        },
        "exchange_rate": {
            "factor_name": "환율",
            "status": "주의",
            "score": 1,
            "evidence": "엔화 환율 상승으로 원화 기준 여행 비용 부담이 커질 수 있습니다.",
            "business_interpretation": "환율 상승은 국제선 여행 비용 부담을 높이는 외부 변수로 작용할 수 있습니다."
        },
        "operation": {
            "factor_name": "운항 상황",
            "status": "보통",
            "score": 0,
            "evidence": "현재 큰 지연 또는 결항 리스크는 확인되지 않았습니다.",
            "business_interpretation": "운항 리스크는 현재 가격 상승 위험도에 큰 영향을 주지 않는 것으로 판단됩니다."
        }
    },

    "limitations": [
        "실제 항공권 판매 가격 데이터는 포함되어 있지 않음",
        "항공사 내부 예약률 및 잔여 좌석 수는 확인할 수 없음",
        "분석 결과는 가격 예측값이 아니라 가격 상승 위험도 판단 결과임"
    ]
}


# =========================
# 2. 입력 데이터 검증 함수
# =========================

def validate_risk_result(data: Dict[str, Any]) -> None:
    required_top_keys = [
        "service",
        "user_query",
        "risk_assessment",
        "factor_analysis",
        "limitations"
    ]

    for key in required_top_keys:
        if key not in data:
            raise ValueError(f"필수 키가 누락되었습니다: {key}")

    required_risk_keys = [
        "risk_score",
        "risk_level",
        "recommendation",
        "confidence",
        "summary"
    ]

    for key in required_risk_keys:
        if key not in data["risk_assessment"]:
            raise ValueError(f"risk_assessment에 필수 키가 누락되었습니다: {key}")

    required_factors = [
        "demand",
        "supply",
        "holiday",
        "exchange_rate",
        "operation"
    ]

    for factor in required_factors:
        if factor not in data["factor_analysis"]:
            raise ValueError(f"factor_analysis에 필수 요인이 누락되었습니다: {factor}")

    valid_risk_levels = ["낮음", "보통", "높음"]
    risk_level = data["risk_assessment"]["risk_level"]

    if risk_level not in valid_risk_levels:
        raise ValueError(f"위험도 등급이 올바르지 않습니다: {risk_level}")

    risk_score = data["risk_assessment"]["risk_score"]

    if not isinstance(risk_score, int):
        raise TypeError("risk_score는 정수여야 합니다.")


# =========================
# 3. LLM 입력용 요인 요약 생성
# =========================

def build_factor_summary(factor_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    factor_order = [
        "demand",
        "supply",
        "holiday",
        "exchange_rate",
        "operation"
    ]

    factor_summary = []

    for factor_key in factor_order:
        factor = factor_analysis[factor_key]

        factor_summary.append({
            "factor": factor["factor_name"],
            "status": factor["status"],
            "score": factor["score"],
            "evidence": factor["evidence"],
            "interpretation": factor["business_interpretation"]
        })

    return factor_summary


# =========================
# 4. LLM 메시지 생성 함수
# =========================

def build_llm_messages(data: Dict[str, Any]) -> List[Dict[str, str]]:
    validate_risk_result(data)

    factor_summary = build_factor_summary(data["factor_analysis"])

    llm_input = {
        "service_context": data["service"],
        "user_query": data["user_query"],
        "risk_assessment": data["risk_assessment"],
        "factor_summary": factor_summary,
        "limitations": data["limitations"]
    }

    system_message = """
너는 항공권 구매 타이밍 의사결정을 지원하는 AI 분석가다.
너의 역할은 공공데이터 기반 위험도 분석 결과를 사용자가 이해할 수 있는 설명으로 변환하는 것이다.

중요 원칙:
- 실제 항공권 가격을 예측하지 않는다.
- 항공권 가격이 반드시 오른다고 단정하지 않는다.
- 사용자의 구매를 강요하지 않는다.
- 공공데이터에 없는 항공사 내부 예약률, 잔여 좌석 수, 실시간 가격 정보를 추정하지 않는다.
- 제공된 분석 결과에 근거한 내용만 설명한다.
- 최종 답변은 소비자가 구매 타이밍을 판단할 수 있도록 구체적이고 실용적으로 작성한다.
"""

    user_message = f"""
아래는 공공데이터 기반 항공권 가격 상승 위험도 분석 결과다.
이 데이터를 바탕으로 사용자에게 항공권 구매 타이밍 판단 결과를 설명하라.

[입력 데이터]
{json.dumps(llm_input, ensure_ascii=False, indent=2)}

[출력 요구사항]
다음 구조로 답변하라.

1. 위험도 요약
- 노선, 출발일, 위험도 등급, 판단 결과를 간결하게 설명

2. 주요 판단 근거
- 수요, 공급, 연휴/시기, 환율, 운항 상황 요인을 구분해 설명
- 각 요인이 왜 가격 상승 위험도에 영향을 줄 수 있는지 설명

3. 구매 타이밍 안내
- 빠른 구매 검토, 지속 확인, 대기 가능 중 현재 판단을 설명
- 단정적 표현 대신 “검토할 수 있습니다”, “가능성이 있습니다” 형태 사용

4. 일정 변경 시 고려할 점
- 연휴 회피, 평일 출발, 대체 공항 또는 대체 날짜 검토 가능성을 제시

5. 유의사항
- 실제 항공권 가격 데이터가 아닌 공공데이터 기반 위험도 분석이라는 점을 명시

[금지 표현]
- “무조건 지금 구매하세요”
- “가격이 반드시 오릅니다”
- “예상 가격은 OOO원입니다”
- “잔여 좌석이 부족합니다”
- “예약률이 높습니다”
"""

    return [
        {"role": "system", "content": system_message.strip()},
        {"role": "user", "content": user_message.strip()}
    ]


# =========================
# 5. LLM 응답 전 단계 테스트용 출력
# =========================

def print_llm_messages(messages: List[Dict[str, str]]) -> None:
    print("\n====================")
    print("LLM SYSTEM MESSAGE")
    print("====================")
    print(messages[0]["content"])

    print("\n====================")
    print("LLM USER MESSAGE")
    print("====================")
    print(messages[1]["content"])


# =========================
# 6. 실행부
# =========================

if __name__ == "__main__":
    messages = build_llm_messages(risk_result)
    print_llm_messages(messages)