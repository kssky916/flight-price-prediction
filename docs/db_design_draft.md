# DB 설계 초안 및 route_features 명세서

## 1. 설계 목적

본 문서는 항공권 구매 타이밍 의사결정 지원 서비스의 데이터 저장 구조와 핵심 분석 테이블인 `route_features`의 설계 기준을 정의한다.

현재 단계는 실제 공공데이터 수집 전이므로, 본 문서는 최종 스키마가 아닌 **DB 설계 초안**이다.  
실제 데이터 수집 후 원천 컬럼명, 데이터 단위, 날짜 기준, 결측값 형태를 확인하여 스키마를 보완한다.

---

## 2. 전체 데이터 흐름

```text
공공데이터/API 수집
→ 원천 데이터 저장
→ 전처리
→ 분석용 피처 생성
→ PostgreSQL 저장
→ 앱/Agent 조회
→ 사용자에게 구매 타이밍 판단 결과 제공
```

본 프로젝트에서는 모든 계산 결과를 DB에 저장하지 않는다.

```text
DB 저장 대상:
- 원천 데이터
- 전처리 데이터
- 최종 분석용 피처 데이터
- 필요 시 분석 로그

인메모리 처리 대상:
- 사용자 단일 요청
- Agent별 계산 결과
- What-if 시뮬레이션 결과
- 목적지 비교 결과
- 화면 표시용 임시 DataFrame
```

---

## 3. PostgreSQL 선택 이유

본 프로젝트는 단순 CRUD 중심 서비스가 아니라, 여러 공공데이터를 수집·정제·결합하여 노선·공항·날짜 단위의 분석 피처를 생성하는 데이터 분석형 서비스이다.

따라서 PostgreSQL을 기본 DB로 사용한다.

| 구분 | PostgreSQL 사용 이유 |
|---|---|
| 분석 쿼리 | 날짜별, 노선별, 공항별 집계와 비교 쿼리에 적합 |
| 데이터 확장성 | 항공통계, 환율, 공휴일, 운항 정보 등 다양한 데이터를 관계형 구조로 관리 가능 |
| JSON 저장 | API 원천 응답, 분석 로그, Agent 결과를 JSONB 형태로 저장 가능 |
| 확장성 | 향후 공항 위치, 노선 거리, 지역 기반 분석으로 확장 시 PostGIS 적용 가능 |
| Python 연동 | pandas, SQLAlchemy, FastAPI, Streamlit과 연동이 용이 |
| 프로젝트 적합성 | 공공데이터 기반 분석 서비스 구조에 적합 |

---

## 4. DB 테이블 구성 초안

현재 단계에서는 테이블을 크게 4개 영역으로 나눈다.

```text
1. raw_* 테이블
2. processed_* 테이블
3. route_features 테이블
4. analysis_logs 테이블
```

---

## 5. raw 테이블

raw 테이블은 공공데이터/API에서 수집한 원천 데이터를 저장한다.  
아직 실제 데이터 컬럼이 확정되지 않았으므로, 원천 응답은 `raw_payload` JSONB 컬럼에 보관한다.

### 예상 raw 테이블

| 테이블명 | 설명 |
|---|---|
| raw_route_stats | 노선별 항공통계 원천 데이터 |
| raw_airport_stats | 공항별 항공통계 원천 데이터 |
| raw_airline_stats | 항공사별 항공통계 원천 데이터 |
| raw_exchange_rates | 환율 정보 원천 데이터 |
| raw_holidays | 공휴일/연휴 정보 원천 데이터 |
| raw_flight_operations | 운항·지연·결항 정보 원천 데이터 |

### raw 테이블 공통 컬럼

| 컬럼명 | 설명 |
|---|---|
| id | 원천 데이터 ID |
| source_name | 데이터 출처명 |
| collected_at | 데이터 수집 시각 |
| reference_date | 데이터 기준일 |
| raw_payload | 원천 응답 JSON |
| created_at | DB 저장 시각 |

---

## 6. processed 테이블

processed 테이블은 원천 데이터를 분석에 사용할 수 있도록 정제한 중간 데이터이다.

예상 처리 작업은 다음과 같다.

```text
- 컬럼명 표준화
- 날짜 형식 통일
- 공항 코드 정리
- 노선 코드 생성
- 결측값 처리
- 중복 제거
- 월별/일별 집계
- 증가율 계산
- Agent 입력 변수 생성
```

### 예상 processed 테이블

| 테이블명 | 설명 |
|---|---|
| processed_route_stats | 노선별 운항편 수, 여객 수, 증가율 정제 데이터 |
| processed_airport_stats | 공항별 여객 수, 공급석 수, 운항편 수 정제 데이터 |
| processed_exchange_rates | 기준 통화별 환율 변화율 정제 데이터 |
| processed_holidays | 공휴일·연휴 날짜 및 인접일 계산용 정제 데이터 |
| processed_flight_operations | 지연율, 결항 건수 등 운항 상태 정제 데이터 |

---

## 7. route_features 테이블

`route_features`는 앱과 Agent가 직접 조회하는 최종 분석용 테이블이다.

현재 MVP의 `data/sample_route_features.csv`는 향후 PostgreSQL의 `route_features` 테이블로 전환한다.

Agent는 원천 데이터를 직접 조회하지 않고, 전처리된 `route_features`를 사용해 위험도를 계산한다.

---

## 8. route_features 명세서

### 테이블 목적

노선·출발일 단위로 항공권 구매 타이밍 판단에 필요한 분석 변수를 저장한다.

### 기본 단위

```text
1 row = 특정 출발공항 + 특정 도착공항 + 특정 출발일 기준 분석 피처
```

예시:

```text
ICN → NRT, 2026-09-25 출발 기준 분석 피처
```

---

## 9. route_features 컬럼 정의

| 컬럼명 | 타입 | 필수 | 설명 |
|---|---|---|---|
| feature_id | BIGSERIAL | Y | 피처 데이터 고유 ID |
| route | VARCHAR(20) | Y | 노선 코드. 예: ICN-NRT |
| departure_airport | VARCHAR(10) | Y | 출발 공항 코드 |
| arrival_airport | VARCHAR(10) | Y | 도착 공항 코드 |
| departure_date | DATE | Y | 출발일 |
| passenger_growth_rate | NUMERIC(6,2) | Y | 여객 수요 증가율 |
| flight_growth_rate | NUMERIC(6,2) | Y | 운항편 증가율 |
| days_to_holiday | INTEGER | Y | 공휴일/연휴까지 남은 일수 |
| holiday_name | VARCHAR(100) | N | 인접 공휴일/연휴명 |
| jpy_krw_change_rate | NUMERIC(6,2) | Y | 엔화 환율 변화율 |
| delay_rate | NUMERIC(6,2) | Y | 최근 운항 지연율 |
| cancel_count | INTEGER | Y | 최근 결항 건수 |
| data_quality_score | NUMERIC(4,2) | N | 데이터 품질 점수 |
| feature_version | VARCHAR(20) | Y | 피처 생성 버전 |
| created_at | TIMESTAMP | Y | 생성 시각 |
| updated_at | TIMESTAMP | Y | 수정 시각 |

---

## 10. route_features 컬럼별 사용 Agent

| 컬럼명 | 사용 Agent | 사용 목적 |
|---|---|---|
| passenger_growth_rate | 수요 Agent | 여객 수요 증가 여부 판단 |
| passenger_growth_rate, flight_growth_rate | 공급 Agent | 수요 대비 운항편 공급 부족 여부 판단 |
| days_to_holiday, holiday_name | 연휴/시기 Agent | 연휴 인접으로 인한 수요 집중 가능성 판단 |
| jpy_krw_change_rate | 환율 Agent | 일본 여행 비용 부담 변화 판단 |
| delay_rate, cancel_count | 운항 상황 Agent | 지연·결항에 따른 운항 리스크 판단 |

---

## 11. route_features 예시 데이터

```csv
route,departure_airport,arrival_airport,departure_date,passenger_growth_rate,flight_growth_rate,days_to_holiday,holiday_name,jpy_krw_change_rate,delay_rate,cancel_count
ICN-NRT,ICN,NRT,2026-09-25,12.5,2.1,2,추석 연휴,3.4,4.2,0
ICN-KIX,ICN,KIX,2026-09-25,7.2,4.8,2,추석 연휴,3.4,3.1,0
ICN-FUK,ICN,FUK,2026-09-25,5.1,5.5,2,추석 연휴,3.4,2.7,0
```

---

## 12. analysis_logs 테이블

`analysis_logs`는 사용자의 분석 요청 결과를 저장하는 선택 테이블이다.  
MVP 단계에서는 CSV 로그로 저장하고, 운영 단계에서 PostgreSQL 테이블로 전환할 수 있다.

### 저장 목적

```text
- 사용자가 자주 조회하는 노선 확인
- 위험도 높은 조건 패턴 분석
- Agent 판단 로직 개선
- LLM 응답 성공/실패 추적
- 서비스 사용성 분석
```

### 저장하지 않을 정보

```text
- 개인정보
- 결제 정보
- 실제 항공권 구매 여부
- 민감한 사용자 정보
```

---

## 13. DB와 인메모리 역할 구분

| 데이터 | 처리 방식 | 이유 |
|---|---|---|
| 공공데이터 원천 응답 | DB 저장 | 재처리, 검증, 추적 필요 |
| 정제된 항공통계 | DB 저장 | 반복 분석에 재사용 |
| 환율/공휴일/운항 정보 | DB 저장 | 여러 노선 분석에 재사용 |
| route_features | DB 저장 | Agent가 직접 조회하는 핵심 데이터 |
| Agent별 위험도 결과 | 인메모리 | 요청마다 계산되는 임시 결과 |
| What-if 일정 변경 결과 | 인메모리 | 화면 표시용 임시 비교 결과 |
| 목적지 비교 결과 | 인메모리 | 요청 시점에 계산되는 비교 결과 |
| LLM 응답 결과 | 기본 인메모리 | 필요 시 로그로만 저장 |

---

## 14. 향후 확정이 필요한 항목

실제 데이터 수집 후 다음 항목을 확정해야 한다.

```text
- 원천 데이터 실제 컬럼명
- 데이터 기준 단위: 일별, 월별, 주별
- 노선 코드 매핑 기준
- 공항 코드 표준화 방식
- 증가율 계산 기준
- 환율 변화율 계산 기간
- 지연율 계산 기준
- 결항 건수 집계 기간
- route_features 생성 주기
- 데이터 품질 점수 산정 방식
```

---

## 15. 결론

현재 단계에서는 `route_features`를 중심으로 DB 설계 초안을 작성한다.

```text
지금 확정 가능한 것:
- Agent가 필요로 하는 최종 피처 컬럼
- DB 저장 대상과 인메모리 처리 대상
- raw / processed / feature / log 구조

데이터 수집 후 보완할 것:
- raw 테이블 상세 컬럼
- processed 테이블 상세 구조
- 증가율 및 지연율 계산 기준
- 인덱스 및 성능 최적화
```

따라서 본 프로젝트의 DB 설계 방향은 다음과 같다.

```text
원천 데이터는 raw 테이블에 보관
정제 데이터는 processed 테이블에 저장
최종 분석 변수는 route_features에 저장
Agent 계산 결과는 기본적으로 인메모리 처리
필요 시 analysis_logs에 분석 결과 저장
```