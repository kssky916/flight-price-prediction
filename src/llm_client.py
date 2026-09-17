import json
import os
from typing import Dict, Any

from dotenv import load_dotenv


load_dotenv()


DEFAULT_MODEL = "gpt-5-mini"


def is_llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


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


def validate_structured_report(report: Dict[str, Any]) -> None:
    required_keys = [
        "headline",
        "one_line_summary",
        "main_reasons",
        "action_guide",
        "alternative_suggestion",
        "caution",
        "display_level",
    ]

    missing_keys = [
        key for key in required_keys
        if key not in report
    ]

    if missing_keys:
        raise ValueError(f"LLM 구조화 응답에 필수 키가 없습니다: {missing_keys}")

    if not isinstance(report["main_reasons"], list):
        raise ValueError("LLM 구조화 응답의 main_reasons는 list여야 합니다.")

    if report["display_level"] not in ["높음", "보통", "낮음"]:
        raise ValueError("LLM 구조화 응답의 display_level 값이 올바르지 않습니다.")


def generate_structured_llm_report(risk_result: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    llm_input = build_llm_input(risk_result)

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "headline": {
                "type": "string",
                "description": "사용자가 바로 이해할 수 있는 한 줄 결론"
            },
            "one_line_summary": {
                "type": "string",
                "description": "노선, 출발일, 구매 판단을 포함한 요약"
            },
            "main_reasons": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
                "description": "판단 근거 목록"
            },
            "action_guide": {
                "type": "string",
                "description": "사용자가 다음에 무엇을 하면 되는지 안내"
            },
            "alternative_suggestion": {
                "type": "string",
                "description": "날짜 변경 또는 목적지 비교 등 대안 제안"
            },
            "caution": {
                "type": "string",
                "description": "가격 예측이 아니라 위험도 판단이라는 유의사항"
            },
            "display_level": {
                "type": "string",
                "enum": ["높음", "보통", "낮음"]
            }
        },
        "required": [
            "headline",
            "one_line_summary",
            "main_reasons",
            "action_guide",
            "alternative_suggestion",
            "caution",
            "display_level"
        ]
    }

    system_prompt = """
너는 항공권 구매 타이밍 의사결정 지원 서비스의 사용자 설명 AI다.

역할:
- Agent가 계산한 위험도 결과를 사용자가 이해할 수 있는 설명으로 바꾼다.
- 결론보다 근거와 행동 가이드를 명확히 전달한다.
- 실제 가격, 예약률, 잔여 좌석 수를 추정하지 않는다.

반드시 지킬 것:
- 제공된 JSON 결과에 있는 정보만 사용한다.
- 가격이 반드시 오른다고 단정하지 않는다.
- 구매를 강요하지 않는다.
- '무조건', '반드시', '예약률', '잔여 좌석 부족', '예상 가격' 같은 표현을 사용하지 않는다.
- 사용자가 다음 행동을 이해할 수 있게 쓴다.
- 반드시 JSON Schema 형식으로만 답한다.
""".strip()

    user_prompt = f"""
아래 JSON은 항공권 구매 타이밍 위험도 분석 결과다.

분석 결과:
{llm_input}

이 결과를 실제 웹서비스 화면에 표시할 수 있는 구조화된 사용자용 설명으로 작성하라.
""".strip()

    response = client.responses.create(
        model=get_openai_model(),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "flight_timing_report",
                "schema": schema,
                "strict": True,
            }
        },
    )

    if not response.output_text:
        raise ValueError("LLM 응답이 비어 있습니다.")

    report = json.loads(response.output_text)
    validate_structured_report(report)

    return report


def generate_llm_report(risk_result: Dict[str, Any]) -> str:
    structured_report = generate_structured_llm_report(risk_result)

    reasons = "\n".join([
        f"- {reason}" for reason in structured_report["main_reasons"]
    ])

    return f"""
### {structured_report["headline"]}

{structured_report["one_line_summary"]}

#### 주요 판단 근거
{reasons}

#### 구매 판단 가이드
{structured_report["action_guide"]}

#### 대안 검토
{structured_report["alternative_suggestion"]}

#### 유의사항
{structured_report["caution"]}
""".strip()