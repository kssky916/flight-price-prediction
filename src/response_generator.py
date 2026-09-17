from typing import Dict, Any, List


def generate_user_response(risk_result: Dict[str, Any]) -> str:
    user_query = risk_result["user_query"]
    risk = risk_result["risk_assessment"]
    factors = risk_result["factor_analysis"]
    limitations = risk_result["limitations"]

    route_name = user_query["route_name"]
    route_code = f'{user_query["departure_airport"]}-{user_query["arrival_airport"]}'
    departure_date = user_query["departure_date"]

    risk_level = risk["risk_level"]
    risk_score = risk["risk_score"]
    recommendation = risk["recommendation"]
    confidence = risk["confidence"]
    summary = risk["summary"]

    response = f"""
# 항공권 구매 타이밍 분석 결과

## 1. 위험도 요약

선택한 노선은 **{route_name} ({route_code})**, 출발일은 **{departure_date}**입니다.

공공데이터 기반 분석 결과, 해당 조건의 항공권 가격 상승 위험도는 **{risk_level}**으로 산정되었습니다.  
위험도 점수는 **{risk_score}점**, 판단 신뢰도는 **{confidence}** 수준입니다.

분석 요약은 다음과 같습니다.

> {summary}

현재 조건에서는 **{recommendation}**가 적절한 판단으로 보입니다.

---

## 2. 주요 판단 근거

### 수요 요인

- 상태: **{factors["demand"]["status"]}**
- 근거: {factors["demand"]["evidence"]}
- 해석: {factors["demand"]["business_interpretation"]}

### 공급 요인

- 상태: **{factors["supply"]["status"]}**
- 근거: {factors["supply"]["evidence"]}
- 해석: {factors["supply"]["business_interpretation"]}

### 연휴/시기 요인

- 상태: **{factors["holiday"]["status"]}**
- 근거: {factors["holiday"]["evidence"]}
- 해석: {factors["holiday"]["business_interpretation"]}

### 환율 요인

- 상태: **{factors["exchange_rate"]["status"]}**
- 근거: {factors["exchange_rate"]["evidence"]}
- 해석: {factors["exchange_rate"]["business_interpretation"]}

### 운항 상황 요인

- 상태: **{factors["operation"]["status"]}**
- 근거: {factors["operation"]["evidence"]}
- 해석: {factors["operation"]["business_interpretation"]}

---

## 3. 구매 타이밍 안내

현재 조건에서는 가격 상승 위험도가 **{risk_level}**으로 산정되었기 때문에, 일정이 고정되어 있다면 항공권 가격을 빠르게 확인하고 구매를 검토하는 것이 적절합니다.

다만 이 결과는 실제 항공권 가격을 직접 예측한 것이 아니라, 공공데이터 기반으로 가격 상승 가능성에 영향을 줄 수 있는 요인을 종합한 위험도 분석 결과입니다.

---

## 4. 일정 변경 시 고려할 점

가격 상승 위험도를 낮추고 싶다면 다음 조건을 함께 검토할 수 있습니다.

- 연휴 직전 또는 직후 출발을 피하기
- 주말보다 평일 출발 검토
- 도쿄 외 오사카, 후쿠오카 등 대체 목적지 비교
- 출발일을 며칠 앞뒤로 조정했을 때 위험도 변화 확인
- 인천 외 김포, 김해 등 다른 출발 공항 가능성 검토

---

## 5. 유의사항

다음 한계가 있습니다.

{chr(10).join([f"- {item}" for item in limitations])}

따라서 최종 구매 전에는 실제 항공권 가격 비교 사이트에서 현재 판매가를 함께 확인하는 것이 필요합니다.
"""

    return response.strip()


if __name__ == "__main__":
    from risk_result import risk_result

    result_text = generate_user_response(risk_result)
    print(result_text)