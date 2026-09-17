import json
import os
from typing import Dict, Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def build_llm_input(risk_result: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "user_query": risk_result["user_query"],
            "risk_assessment": risk_result["risk_assessment"],
            "factor_analysis": risk_result["factor_analysis"],
            "limitations": risk_result["limitations"],
        },
        ensure_ascii=False,
        indent=2,
    )


def generate_llm_report(risk_result: Dict[str, Any]) -> str:
    llm_input = build_llm_input(risk_result)

    system_prompt = """
너는 항공권 구매 타이밍 의사결정을 지원하는 AI 분석가다.
너의 역할은 공공데이터 기반 위험도 분석 결과를 사용자가 이해하기 쉬운 설명으로 변환하는 것이다.

반드시 지켜야 할 원칙:
- 실제 항공권 가격을 예측하지 않는다.
- 가격이 반드시 오른다고 단정하지 않는다.
- 사용자의 구매를 강요하지 않는다.
- 항공사 내부 예약률, 잔여 좌석 수, 실시간 가격 정보를 추정하지 않는다.
- 제공된 분석 결과에 근거한 내용만 설명한다.
- 최종 답변은 한국어 Markdown 형식으로 작성한다.
""".strip()

    user_prompt = f"""
아래 JSON은 항공권 가격 상승 위험도 분석 결과다.

[분석 결과 JSON]
{llm_input}

다음 형식으로 사용자용 리포트를 작성하라.

# 항공권 구매 타이밍 분석 결과

## 1. 위험도 요약
- 노선, 출발일, 위험도 등급, 구매 판단을 요약한다.

## 2. 주요 판단 근거
- 수요, 공급, 연휴/시기, 환율, 운항 상황 요인을 구분해 설명한다.
- 각 요인이 가격 상승 위험도에 어떤 영향을 줄 수 있는지 설명한다.

## 3. 구매 타이밍 안내
- 빠른 구매 검토, 가격 변동 지속 확인, 대기 가능 중 현재 판단을 설명한다.
- 단정하지 말고 가능성 중심으로 표현한다.

## 4. 일정 변경 시 고려할 점
- 연휴 회피, 평일 출발, 대체 공항 또는 대체 날짜 검토 가능성을 제시한다.

## 5. 유의사항
- 실제 항공권 가격 데이터가 아닌 공공데이터 기반 위험도 분석이라는 점을 명시한다.

금지 표현:
- “무조건 지금 구매하세요”
- “가격이 반드시 오릅니다”
- “예상 가격은 OOO원입니다”
- “잔여 좌석이 부족합니다”
- “예약률이 높습니다”
""".strip()

    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.output_text