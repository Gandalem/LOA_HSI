# LOAWA 기반 캐릭터 Seed 수집 설계

## 1. 목적

이 문서는 `LOA_HSI`에서 `LOAWA`를 **공식 데이터 소스**가 아니라 **캐릭터 발견용 seed 인덱스**로 사용하는 방식을 정의한다.

원칙:

- 캐릭터 이름 후보는 `LOAWA`에서 수집할 수 있다.
- 실제 캐릭터 상태 원본은 반드시 로스트아크 공식 API에서 가져온다.
- `LOAWA` 응답은 보조 메타데이터와 샘플링 기준으로만 사용한다.
- 대량 수집은 전수보다 **계층 샘플링 + 장기 누적**을 우선한다.

## 2. 왜 LOAWA seed가 필요한가

`LOA_HSI`의 가장 큰 초기 병목은 “어떤 캐릭터를 조회할 것인가”이다.

`LOAWA`에는 다음과 같은 공개 필터 기반 탐색 화면이 있다.

- 전투력 랭킹: `/rank/combatpower`
- 중앙값 통계: `/stat/median`

사용자 확인 기준으로 `https://loawa.com/stat/median`에는 **대상 1,187,587명**이 표시된다. 이 수치는 `LOA_HSI` 입장에서 매우 큰 캐릭터 후보 풀을 의미한다.

이 숫자의 해석은 다음과 같다.

- 1,187,587명은 `LOAWA`가 노출하는 탐색 가능한 캐릭터 풀이다.
- 이것이 곧바로 `LOA_HSI`의 공식 원본 데이터셋은 아니다.
- `LOA_HSI`는 이 후보 풀에서 이름을 얻고, 이후 공식 API로 검증 및 정규화한다.

## 3. 역할 분리

### LOAWA 역할

- 캐릭터 이름 seed 확보
- 서버/직업/전투력/아이템레벨 기준의 모집단 분해
- 대표 캐릭터 여부 등 공개 필터 메타데이터 수집

### 공식 Lost Ark API 역할

- 캐릭터 프로필/장비/각인/아크패시브 조회
- 비용 계산 입력 생성
- 원본 저장과 재현성 보장

### LOA_HSI 역할

- 공식 API 원본 보관
- 장신구/스톤/팔찌 비용 재현
- 경매장 `Options` 검증
- 시뮬레이션 및 Parquet/DuckDB 적재

## 4. Seed 수집 목표

`LOAWA`에서 바로 모든 캐릭터를 한 번에 긁는 방식은 권장하지 않는다.

권장 목표는 아래 3단계다.

### Phase A. Seed 인덱스 구축

- 서버별
- 직업별
- 포지션별
- 전투력 구간별
- 아이템레벨 구간별
- 대표 캐릭터 여부별

이 기준으로 캐릭터 이름과 랭킹 맥락을 수집한다.

### Phase B. 공식 API 검증

각 seed에 대해 공식 API 조회를 수행하고 다음 상태로 분류한다.

- `api_ok`
- `api_not_found`
- `api_private_or_hidden`
- `api_rate_limited`
- `api_parse_failed`

### Phase C. 연구 배치 생성

공식 API 검증을 통과한 캐릭터만 `LOA_HSI` 데이터셋과 시뮬레이션 배치에 투입한다.

## 5. Seed 테이블 설계

### 5.1 Raw seed index

테이블명:

- `loawa_seed_index`

주요 컬럼:

- `seed_id`
- `collected_at`
- `source_page`
- `source_type`
- `server_name`
- `class_name`
- `position`
- `character_name`
- `item_level_text`
- `combat_power_text`
- `rank_value`
- `representative_only_filter`
- `level_band`
- `page_no`
- `raw_path`
- `request_hash`

설명:

- `source_type` 예: `combatpower_rank`, `median_stat`
- `representative_only_filter`는 해당 수집 배치가 “대표 캐릭터만” 필터를 사용했는지 나타낸다.

### 5.2 Seed canonical table

테이블명:

- `loawa_seed_canonical`

주요 컬럼:

- `canonical_character_name`
- `latest_server_name`
- `latest_class_name`
- `first_seen_at`
- `last_seen_at`
- `seen_count`
- `seen_sources`
- `seen_servers`
- `representative_seen_count`
- `non_representative_seen_count`
- `api_status`
- `api_last_checked_at`
- `api_raw_path`

설명:

- 여러 배치에서 반복 노출된 캐릭터를 하나의 canonical row로 합친다.
- 이후 공식 API 조회 대상을 이 테이블에서 뽑는다.

## 6. 샘플링 축

`LOAWA` seed 수집은 무작위가 아니라 명시적 층화 기준을 가져야 한다.

권장 층화 축:

- 서버
- 직업
- 포지션
- 대표 캐릭터 여부
- 아이템레벨 구간
- 전투력 구간

### 예시 서버 축

- 니나브
- 루페온
- 실리안
- 아만
- 아브렐슈드
- 카단
- 카마인
- 카제로스

### 예시 아이템레벨 구간

- 1300-1499
- 1500-1589
- 1590-1649
- 1650-1689
- 1690-1719
- 1720+

### 예시 전투력 구간

- 상위 랭킹
- 중앙값 근처
- 중앙값 이하

중앙값 페이지는 “평균적인 세팅대”를 확보하는 데, 전투력 랭킹은 “상위 고투자 세팅대”를 확보하는 데 유리하다.

## 7. Seed 수집 전략

### 전략 A. 상위 랭킹 집중

목적:

- 고강화/고세팅 캐릭터 확보
- 장신구/스톤/팔찌 비용이 큰 샘플 우선 확보

소스:

- `/rank/combatpower`

장점:

- 고비용 세팅을 빠르게 모을 수 있다.

단점:

- 모집단 편향이 크다.

### 전략 B. 중앙값 기준 분산 수집

목적:

- 일반 플레이어 분포 확보
- 비용 모델의 보편성 검증

소스:

- `/stat/median`

장점:

- 과도한 상위권 편향을 줄인다.

단점:

- 상위 고가 세팅 샘플 밀도가 낮다.

### 전략 C. 혼합 전략

실전 권장안:

- 40%: 전투력 랭킹 기반
- 40%: 중앙값 통계 기반
- 20%: 서버/직업 희소 구간 보정 샘플

## 8. 수집 단위

한 번의 수집 작업은 아래 단위로 나눈다.

- 페이지 단위
- 필터 조합 단위
- 날짜/시간 단위

하나의 수집 레코드는 아래를 함께 남긴다.

- 요청 URL
- 적용 필터
- 수집 시각
- 페이지 번호
- 추출 캐릭터 수
- raw 응답 경로

## 9. 중복 제거 규칙

같은 캐릭터명이 여러 배치에서 반복 등장할 수 있다.

규칙:

1. `character_name + server_name` 조합을 1차 키로 사용한다.
2. 서버가 비어 있거나 변경되면 최근 공식 API 결과를 우선한다.
3. 같은 캐릭터가 랭킹/중앙값 양쪽에서 보이면 `seen_sources`에 둘 다 기록한다.
4. 대표 캐릭터 필터 여부는 별도 count로 유지한다.

## 10. 대표 캐릭터 필터 처리

`LOAWA` 중앙값 페이지에는 `대표 캐릭터만` 필터가 존재한다.

이 필터는 매우 중요하다.

- `대표 캐릭터만=true`
  - 계정의 주력 캐릭터 비중이 높을 가능성
  - 중복 부캐 편향을 줄이는 데 유리
- `대표 캐릭터만=false`
  - 전체 플레이어 분포를 넓게 보는 데 유리

권장 수집 비율:

- 70%: `대표 캐릭터만=true`
- 30%: `대표 캐릭터만=false`

## 11. 공식 API 조회 우선순위

seed가 많아도 공식 API는 무한정 호출하면 안 된다.

우선순위 큐를 둔다.

### 1순위

- 대표 캐릭터
- 상위 전투력
- 직업/서버 희소 구간
- 최근 7일 내 미검증 seed

### 2순위

- 중앙값 근처 일반 표본

### 3순위

- 오래된 seed 재검증
- 비대표/저우선순위 seed

## 12. Seed에서 API로 넘어가는 상태 머신

각 canonical seed는 아래 상태를 가진다.

- `discovered`
- `queued_for_api`
- `api_ok`
- `api_not_found`
- `api_private_or_hidden`
- `api_failed_retryable`
- `api_failed_terminal`

재시도 정책:

- `api_rate_limited`: 짧은 backoff 후 재시도
- `api_parse_failed`: 코드 수정 전까지 보류
- `api_not_found`: 주기적 저빈도 재검증

## 13. Seed 데이터 저장 위치

50GB 설계와 동일하게 seed 데이터도 외부 루트에 둔다.

예시:

```text
E:\loa-hsi-data
  raw
    loawa
      combatpower
        date=YYYY-MM-DD
          hour=HH
            server=SERVER
              class=CLASS
                page=0001.json.zst
      median
        date=YYYY-MM-DD
          hour=HH
            representative_only=true
              server=SERVER
                class=CLASS
                  page=0001.json.zst
  parquet
    loawa_seed_index
      date=YYYY-MM-DD
        part-0001.parquet
    loawa_seed_canonical
      date=YYYY-MM-DD
        part-0001.parquet
```

## 14. 권장 수집 주기

### Seed 수집

- 전투력 랭킹: 하루 1~2회
- 중앙값 통계: 하루 1회

### 공식 API 검증

- 신규 seed: 매일
- 기존 seed 재검증: 3~7일 주기

### 희소 구간 보정

- 서버/직업 조합 중 데이터가 적은 층은 별도 주간 보정 배치

## 15. 50GB 수집과의 연결

`LOAWA` seed 수집은 50GB 자체를 직접 채우기 위한 단계가 아니라, 뒤쪽 3단계를 안정화하기 위한 기반이다.

- 더 많은 캐릭터 상태 raw 확보
- 더 다양한 장신구/스톤/팔찌 구조 확보
- 더 큰 시뮬레이션 입력 풀 확보

즉 `LOAWA`는 50GB 데이터셋에서 다음 역할을 한다.

- Raw source discovery layer
- Sampling control layer
- Coverage balancing layer

## 16. 품질 검증

seed 수집 후 아래 검사를 수행한다.

- 배치별 캐릭터 수 > 0
- 서버/직업 필터 메타데이터 누락 없음
- 중복률 계산 가능
- 대표 캐릭터 여부 필터 저장 여부 확인
- 같은 날 수집 배치 간 이름 중복률 계산
- canonical 병합 후 `first_seen_at`, `last_seen_at` 정상 갱신

공식 API 연결 후 추가 검사:

- seed 대비 `api_ok` 비율
- 서버별 `api_ok` 비율
- 직업별 `api_ok` 비율
- 대표/비대표 간 성공률 차이

## 17. 구현 우선순위

### Phase 1

- seed 스키마 정의
- 외부 저장 경로 정의
- raw archive 포맷 정의

### Phase 2

- `LOAWA` seed 수집기 추가
- canonical 병합기 추가
- API 검증 큐 추가

### Phase 3

- seed 기반 공식 API 배치 수집기 추가
- 수집 커버리지 리포트 추가

### Phase 4

- `LOA_HSI` 시뮬레이션 배치와 연결
- 직업/서버/전투력 구간별 실험 시나리오 자동 생성

## 18. 최종 기준

`LOAWA` seed 수집이 성공했다는 것은 단순히 이름을 많이 모았다는 뜻이 아니다.

아래를 만족해야 한다.

- 캐릭터 이름 후보 풀이 충분히 넓다
- 서버/직업/전투력 구간 편향을 통제할 수 있다
- 공식 API 검증으로 넘어갈 우선순위를 관리할 수 있다
- 50GB 연구 데이터셋의 입력 모집단을 설명할 수 있다

이 기준을 만족하면 `LOA_HSI`는 임의 조회 기반이 아니라, **공개 캐릭터 모집단을 체계적으로 샘플링하는 데이터 분석 시스템**이 된다.
