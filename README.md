# 항공권 가격 상승 위험도 및 구매 타이밍 판단 서비스

공공데이터를 기반으로 항공 노선의 수요, 운항 공급, 노선 경쟁도, 환율, 공휴일 요인을 분석하여 항공권 가격 상승 위험도와 구매 타이밍 판단을 지원하는 서비스입니다.

본 프로젝트는 실제 항공권 가격 이력 데이터가 제한적인 상황에서, 항공권 가격에 영향을 줄 수 있는 공공 지표를 활용해 소비자의 구매 의사결정을 보조하는 것을 목표로 합니다.

---

## 1. 프로젝트 개요

항공권 가격은 수요 증가, 운항 공급 부족, 환율 변동, 특정 노선의 항공사 경쟁도, 공휴일 및 연휴 수요에 영향을 받습니다.

본 서비스는 이러한 요인을 공공데이터 기반으로 정제하고, 노선별 가격 상승 압력 점수를 산정하여 다음과 같은 결과를 제공합니다.

- 가격 상승 위험도: 높음 / 중간 / 낮음
- 구매 타이밍 판단: 빠른 구매 검토 / 가격 모니터링 후 구매 / 대기 가능
- 수요·공급·경쟁도·환율·공휴일 기반 판단 근거
- 자연어 여행 조건 기반 추천 노선 및 일정
- AI 기반 분석 결과 설명

---

## 2. 문제 정의

소비자는 항공권을 구매할 때 다음과 같은 어려움을 겪습니다.

- 현재 항공권을 바로 구매해야 하는지 판단하기 어려움
- 가격이 오를 가능성이 있는지 알기 어려움
- 노선별 수요와 공급 상황을 직접 확인하기 어려움
- 환율, 공휴일, 노선 경쟁도 같은 외부 요인을 종합적으로 보기 어려움
- 여행 일정이 연휴와 겹칠 때 가격 상승 위험이 얼마나 커지는지 판단하기 어려움

따라서 본 프로젝트는 공공데이터를 활용해 항공권 가격 상승 위험도를 정량화하고, 구매 타이밍 판단을 지원하는 MVP를 구현했습니다.

---

## 3. 활용 데이터

### 3.1 항공통계 노선 데이터

- 파일: `항공통계상세조회(노선)`
- 기간: 2021년 ~ 2025년
- 주요 컬럼:
  - 노선1
  - 노선2
  - 운항(편)
  - 여객(명)
  - 화물(톤)
- 활용 목적:
  - 노선별 여객 증가율 산출
  - 노선별 운항편 증가율 산출
  - 편당 탑승객 수 산출
  - 노선별 수요·공급 흐름 분석

### 3.2 인천공항 항공사별 노선별 운송실적

- 파일: `인천국제공항공사_항공사별 노선별 운송실적`
- 기간: 2022년 ~ 2026년 일부
- 주요 컬럼:
  - 항공사명
  - 노선
  - 국가
  - 공항
  - 운항(편)
  - 유임승객(명)
- 활용 목적:
  - 일본 노선별 운항 항공사 수 산출
  - LCC 비중 산출
  - 노선 경쟁도 분석

### 3.3 지역/국가별 항공통계

- 파일: `항공통계상세조회(지역_국가)`
- 기간: 2022년 ~ 2026년 일부
- 활용 목적:
  - 일본 전체 여객 수요 흐름 확인
  - 국가 단위 수요 증가율 보조 변수 생성

### 3.4 항공사별 항공통계

- 파일: `항공통계상세조회(항공사)`
- 기간: 2022년 ~ 2026년 일부
- 활용 목적:
  - 항공사별 공급석, 운항편, 여객 규모 확인
  - 항공사 규모 및 공급 수준 보조 변수 생성

### 3.5 공휴일 데이터

- 파일: `processed_holidays.csv`, `processed_holidays_clean.csv`
- 활용 목적:
  - 공휴일 및 연휴 변수 생성
  - 여행 기간과 주요 공휴일의 겹침 여부 계산
  - 일정 기반 가격 상승 압력 반영

### 3.6 환율 데이터

- 파일: `한국무역보험공사_환율`
- 활용 목적:
  - JPY/KRW 환율 변동률 산출
  - 일본 노선 여행 비용 부담 요인 반영

---

## 4. 데이터 파이프라인

본 프로젝트의 데이터 처리 흐름은 다음과 같습니다.

```text
원본 데이터 수집
↓
data/raw/ 저장
↓
데이터별 정제 스크립트 실행
↓
data/processed/ 정제 파일 생성
↓
노선·경쟁도·국가·환율·공휴일 데이터 통합
↓
route_features_japan.csv 생성
↓
FastAPI 분석 API 및 Streamlit 화면에서 활용
```

주요 처리 스크립트는 다음과 같습니다.

```text
scripts/clean_route_stats.py
→ 항공통계 노선 데이터 정제

scripts/clean_icn_airline_route_stats.py
→ 인천공항 항공사별 노선별 운송실적 정제

scripts/clean_country_stats.py
→ 국가별 항공통계 정제

scripts/clean_airline_stats.py
→ 항공사별 항공통계 정제

scripts/clean_holidays.py
→ 공휴일 데이터 정제

scripts/clean_exchange_rates.py
→ 환율 데이터 정제

scripts/build_route_features.py
→ 최종 노선별 분석 피처 생성
```

최종 분석 파일은 다음 경로에 생성됩니다.

```text
data/processed/route_features_japan.csv
```

---

## 5. 서비스 구조

본 프로젝트는 Streamlit 기반 사용자 화면과 FastAPI 기반 분석 API를 분리한 구조로 구성되어 있습니다.

```text
사용자 입력
↓
Streamlit UI
↓
FastAPI API 요청
↓
데이터 로드 및 위험도 산정
↓
AI 기반 설명 생성
↓
결과 반환 및 화면 출력
```

### 주요 구성 파일

```text
app.py
→ Streamlit 기반 사용자 화면

api/main.py
→ FastAPI 백엔드 API 서버

src/api_client.py
→ Streamlit에서 FastAPI를 호출하는 클라이언트

src/data_loader.py
→ 정제 데이터 로드 및 노선 피처 조회

src/risk_normalizer.py
→ 위험도 산정용 피처 정규화

src/agents.py
→ Rule-based 위험도 점수 계산

src/travel_recommender.py
→ 자연어 여행 조건 기반 후보 노선 및 일정 추천

src/response_generator.py
→ 위험도 결과 기반 사용자 설명 생성

src/llm_client.py
→ AI 모델 호출 및 자연어 조건 추출

src/analysis_logger.py
→ 분석 결과 로그 저장
```

---

## 6. 주요 기능

### 6.1 노선별 위험도 분석

사용자가 출발 공항, 도착 공항, 출발일, 도착일을 입력하면 해당 노선의 가격 상승 위험도를 계산합니다.

분석 결과는 다음 정보를 포함합니다.

- 위험도 점수
- 위험도 등급
- 구매 타이밍 판단
- 수요·공급·경쟁도·공휴일·환율 요인별 점수
- AI 기반 판단 근거 설명

### 6.2 자연어 기반 여행 조건 추천

사용자가 자연어로 여행 조건을 입력하면 AI가 조건을 추출하고, 가능한 노선과 여행 일정을 추천합니다.

입력 예시:

```text
내년 추석 일본여행 갈거야 3박4일로 추천좀
```

처리 흐름:

```text
자연어 입력
↓
여행 조건 추출
↓
여행 가능 날짜 후보 생성
↓
노선별 위험도 산정
↓
추천 노선 및 구매 타이밍 반환
```

### 6.3 공휴일 포함 일정 판단

설날, 추석, 크리스마스 등 주요 공휴일이 여행 기간에 포함되는 경우 일정/공휴일 압력을 반영합니다.

단순히 공휴일이 포함되었는지만 보는 것이 아니라, 여행 기간에 포함된 주요 공휴일 일수 비율을 기준으로 점수를 계산합니다.

예시:

```text
추석 연휴 3일 중 1일 포함 → 일정/공휴일 압력 5점
추석 연휴 3일 중 2일 포함 → 일정/공휴일 압력 10점
추석 연휴 3일 모두 포함 → 일정/공휴일 압력 15점
```

---

## 7. 위험도 산정 방식

본 프로젝트는 실제 항공권 가격을 직접 예측하는 모델이 아니라, 공공데이터를 기반으로 항공권 가격 상승 가능성에 영향을 줄 수 있는 요인을 점수화한 **가격 상승 압력 지표**를 산정하는 방식으로 설계했습니다.

위험도 점수는 총 100점 기준이며, 다음 5개 요인을 합산해 계산합니다.

| 구분 | 가중치 | 설명 |
|---|---:|---|
| 수요 압력 | 35점 | 승객 증가율과 편당 탑승객 수를 기반으로 수요 강도를 판단 |
| 공급 제약 | 25점 | 운항편 증가율이 낮을수록 공급이 충분히 늘지 않는 것으로 판단 |
| 경쟁도 압력 | 20점 | 항공사 수와 LCC 비중이 낮을수록 가격 경쟁 압력이 약한 것으로 판단 |
| 일정/공휴일 압력 | 15점 | 여행 기간이 주요 공휴일과 겹치는 정도를 반영 |
| 환율 압력 | 5점 | 일본 노선 기준 JPY/KRW 환율 변동률을 보조 요인으로 반영 |

각 피처는 단위가 다르기 때문에 원시값을 그대로 합산하지 않고, **동일 연도 내 일본 노선 후보군 기준 percentile 정규화**를 적용했습니다.

이를 통해 승객 증가율, 운항편 증가율, 항공사 수, LCC 비중처럼 단위가 다른 지표를 동일한 0~1 범위의 상대 점수로 변환했습니다.

### 7.1 요인별 산정 방식

#### 수요 압력

수요 압력은 다음 지표를 기반으로 계산합니다.

- 여객 증가율
- 편당 탑승객 수

여객 증가율이 높거나 편당 탑승객 수가 높을수록 수요 압력이 큰 것으로 판단합니다.

#### 공급 제약

공급 제약은 운항편 증가율을 기반으로 계산합니다.

운항편 증가율이 낮을수록 수요 증가에 비해 공급이 충분히 늘지 않는 것으로 판단하고, 가격 상승 압력을 높게 반영합니다.

#### 경쟁도 압력

경쟁도 압력은 다음 지표를 기반으로 계산합니다.

- 노선별 운항 항공사 수
- LCC 비중

운항 항공사 수가 적거나 LCC 비중이 낮을수록 가격 경쟁이 약한 것으로 판단합니다.

#### 일정/공휴일 압력

일정/공휴일 압력은 여행 기간에 포함된 주요 공휴일 일수 비율을 기반으로 계산합니다.

예를 들어 추석 연휴 3일 중 1일만 여행 기간에 포함되면 5점, 3일 모두 포함되면 15점을 반영합니다.

#### 환율 압력

환율 압력은 일본 노선 기준 JPY/KRW 환율 변동률을 기반으로 계산합니다.

환율은 항공권 가격 자체뿐 아니라 여행 비용 부담에도 영향을 줄 수 있으므로 보조 요인으로 반영했습니다.

### 7.2 위험도 등급 기준

최종 점수에 따라 구매 타이밍은 다음과 같이 분류합니다.

| 위험도 점수 | 위험도 | 구매 타이밍 판단 |
|---:|---|---|
| 60점 이상 | 높음 | 빠른 구매 검토 |
| 40점 이상 60점 미만 | 중간 | 가격 모니터링 후 구매 |
| 40점 미만 | 낮음 | 대기 가능 |

---

## 8. API 명세

### 8.1 Health Check

```http
GET /health
```

FastAPI 서버 실행 상태를 확인합니다.

### 8.2 노선별 위험도 분석

```http
POST /analyze/route
```

입력 예시:

```json
{
  "departure_airport": "ICN",
  "arrival_airport": "NRT",
  "departure_date": "2027-09-13",
  "return_date": "2027-09-16"
}
```

응답 주요 정보:

```text
- 위험도 점수
- 위험도 등급
- 구매 타이밍 판단
- 요인별 점수
- AI 기반 설명
```

### 8.3 텍스트 기반 여행 조건 추천

```http
POST /recommend/text
```

입력 예시:

```json
{
  "text": "내년 추석 일본여행 갈거야 3박4일로 추천좀",
  "recommendation_count": 5
}
```

응답 주요 정보:

```text
- 추출된 여행 조건
- 추천 노선
- 추천 출발일 및 도착일
- 노선별 위험도 점수
- 구매 타이밍 판단
- AI 기반 설명
```

---

## 9. 실행 방법

### 9.1 가상환경 생성 및 패키지 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 9.2 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 값을 설정합니다.

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5-mini
```

### 9.3 백엔드 API 서버 실행

```bash
./scripts/run_backend.sh
```

API 문서 확인:

```text
http://127.0.0.1:8000/docs
```

### 9.4 Streamlit UI 실행

새 터미널을 열고 다음 명령어를 실행합니다.

```bash
source .venv/bin/activate
./scripts/run_frontend.sh
```

Streamlit 화면 접속:

```text
http://localhost:8501
```

---

## 10. 프로젝트 구조

```text
.
├── README.md
├── api
│   ├── __init__.py
│   └── main.py
├── app.py
├── data
│   ├── processed
│   │   ├── processed_airline_stats.csv
│   │   ├── processed_country_stats.csv
│   │   ├── processed_country_stats_japan.csv
│   │   ├── processed_exchange_rates_daily.csv
│   │   ├── processed_holidays.csv
│   │   ├── processed_holidays_clean.csv
│   │   ├── processed_icn_airline_route_stats.csv
│   │   ├── processed_icn_airline_route_stats_japan.csv
│   │   ├── processed_icn_route_competition_japan.csv
│   │   ├── processed_icn_weekly_departures.csv
│   │   ├── processed_route_stats.csv
│   │   ├── processed_route_stats_japan.csv
│   │   └── route_features_japan.csv
│   └── sample_route_features.csv
├── docs
│   ├── db_design_draft.md
│   ├── 데이터 가이드.md
│   └── 사업계획서 초안.md
├── outputs
│   ├── analysis_logs.csv
│   ├── purchase_timing_report.md
│   └── risk_result.json
├── requirements.txt
├── scripts
│   ├── build_route_features.py
│   ├── check_risk_feature_distribution.py
│   ├── clean_airline_stats.py
│   ├── clean_country_stats.py
│   ├── clean_exchange_rates.py
│   ├── clean_holidays.py
│   ├── clean_icn_airline_route_stats.py
│   ├── clean_route_stats.py
│   ├── preview_normalized_risk_score.py
│   ├── run_backend.sh
│   ├── run_frontend.sh
│   ├── run_pipeline.py
│   ├── test_llm.py
│   ├── test_travel_parser.py
│   └── test_travel_recommender.py
└── src
    ├── __init__.py
    ├── agents.py
    ├── analysis_logger.py
    ├── api_client.py
    ├── data_loader.py
    ├── fallback_report.py
    ├── llm_client.py
    ├── prompt_builder.py
    ├── query_parser.py
    ├── response_generator.py
    ├── risk_normalizer.py
    ├── route_comparator.py
    ├── scenario_simulator.py
    ├── travel_recommender.py
    └── validators.py
```

---

## 11. 방법론적 한계 및 향후 개선

현재 위험도 점수는 실제 항공권 운임 이력 데이터로 학습된 예측 모델이 아니라, 공공데이터 기반의 초기 Rule-based 휴리스틱 모델입니다.

따라서 산출 결과는 특정 항공권의 실제 가격 상승률이나 최저가를 예측하는 값이 아니라, 노선별 수요·공급·경쟁도·일정·환율 요인을 종합한 가격 상승 압력 지표로 해석해야 합니다.

현재 가중치는 실제 가격 데이터 기반 회귀분석이나 백테스트를 통해 도출된 계수가 아니라, 프로젝트 초기 단계에서 각 요인의 상대적 중요도를 반영해 설정한 기준값입니다.

향후 실제 항공권 가격 이력 데이터가 확보된다면, 과거 특정 시점의 위험도 점수와 이후 가격 변동률을 비교하는 방식으로 가중치의 타당성을 검증하고 보정할 수 있습니다.

정규화 기준은 동일 연도 내 일본 노선 후보군으로 한정했습니다. 이 방식은 사용자가 일본 여행 조건을 입력했을 때 후보 노선 간 구매 우선순위를 비교하는 데 적합하지만, 표본 수가 적은 연도에서는 percentile 값이 민감하게 변할 수 있습니다.

결측값 또는 동일값이 반복되는 피처는 중립값으로 처리해 과도한 왜곡을 줄였습니다.

현재 환율 변수는 일본 노선에 맞춰 JPY/KRW 변동률을 사용합니다. 향후 일본 외 국가 노선으로 확장할 경우, 목적지 국가 또는 통화 코드에 따라 USD/KRW, EUR/KRW 등 통화별 환율 변수를 동적으로 적용하는 구조로 일반화할 필요가 있습니다.

향후 개선 방향은 다음과 같습니다.

- 실제 항공권 가격 이력 데이터 확보 후 위험도 점수와 가격 변동률 간 상관성 검증
- 회귀분석 또는 백테스트 기반 가중치 보정
- 노선 표본 수가 적은 경우를 고려한 정규화 fallback 기준 고도화
- 국가별 통화 변수 일반화
- 실시간 운임, 좌석 잔여량, 항공사 프로모션 데이터 연동
- 자연어 입력 의도에 따른 일정 추천 전략 세분화