import os
from pathlib import Path
from typing import Dict, Any

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)


def is_llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def build_llm_prompt(risk_result: Dict[str, Any]) -> str:
    factor_details = risk_result.get("factor_details", [])
    evidence = risk_result.get("evidence", [])

    factor_lines = []
    for item in factor_details:
        factor_lines.append(
            f"- {item.get('factor')}: {item.get('score')}/{item.get('max_score')}점, {item.get('reason')}"
        )

    evidence_lines = []
    for item in evidence[:10]:
        evidence_lines.append(f"- {item}")

    return f"""
너는 항공권 구매 타이밍 판단 서비스의 설명 생성 담당자다.

아래 분석 결과를 사용자가 이해하기 쉽게 설명해라.

반드시 지켜야 할 규칙:
- 실제 항공권 가격을 예측했다고 말하지 마라.
- LLM이 직접 판단했다고 말하지 마라.
- 데이터 기반 점수화 로직의 결과를 설명하는 역할로만 작성해라.
- 과장하지 마라.
- 한국어로 작성해라.
- 짧고 명확하게 작성해라.

[분석 결과]
노선: {risk_result.get("departure_airport")} → {risk_result.get("arrival_airport")}
출발일: {risk_result.get("departure_date")}
위험도: {risk_result.get("risk_level")}
위험도 점수: {risk_result.get("risk_score")} / {risk_result.get("max_score")}
구매 판단: {risk_result.get("purchase_timing_recommendation")}
판단 요약: {risk_result.get("decision_reason")}

[요인별 점수]
{chr(10).join(factor_lines)}

[사용 데이터]
{chr(10).join(evidence_lines)}

아래 형식으로만 작성해라.

### LLM 기반 구매 타이밍 설명

#### 1. 현재 판단
- 현재 구매 판단을 한 문장으로 설명

#### 2. 주요 근거
- 핵심 근거 3개를 bullet로 설명

#### 3. 해석
- 왜 이런 판단이 나왔는지 2~3문장으로 설명

#### 4. 최종 판단
- 지금 구매, 모니터링, 대기 중 하나로 명확하게 설명
""".strip()


def _extract_text_from_response(data: Dict[str, Any]) -> str:
    if "output_text" in data and data["output_text"]:
        return data["output_text"]

    output = data.get("output", [])

    texts = []

    for item in output:
        content = item.get("content", [])

        for content_item in content:
            if content_item.get("type") in ["output_text", "text"]:
                text = content_item.get("text", "")
                if text:
                    texts.append(text)

    if texts:
        return "\n".join(texts)

    raise ValueError(f"LLM 응답에서 텍스트를 찾지 못했습니다: {data}")


def generate_llm_explanation(risk_result: Dict[str, Any]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    prompt = build_llm_prompt(risk_result)

    url = "https://api.openai.com/v1/responses"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": prompt,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        raise ValueError(f"OpenAI API 오류 {response.status_code}: {response.text}")

    data = response.json()

    return _extract_text_from_response(data)