# LOA-HSI 50GB 데이터 수집 설계

## 1. 목표

이 설계의 목적은 `LOA_HSI`를 다음 기준에 맞는 **재현 가능한 대용량 데이터 분석 시스템**으로 확장하는 것이다.

- 실제 로스트아크 API 응답과 공식 확률표를 바탕으로 한다.
- 장신구, 어빌리티 스톤, 팔찌의 **경매장 검증 로직**을 raw 응답 수준에서 다시 확인할 수 있어야 한다.
- GitHub 저장소에는 코드, 샘플, 설계, 결과 예시만 넣고, **50GB급 실데이터는 외부 디렉터리**에 보관한다.
- 동일 캐릭터 최신 1개만 남기는 운영 캐시와 별개로, **히스토리 누적형 연구 데이터셋**을 별도로 유지한다.

## 2. 현재 코드 기준 제약

현재 저장소에는 대용량 축적을 막는 정책이 이미 들어 있다.

- `backend/app/services/dataset_writer.py`
  - 같은 캐릭터의 이전 Parquet를 지우고 `latest_per_character`만 유지한다.
- `backend/app/services/simulation_store.py`
  - 동일 입력은 `cache_key`로 중복 저장을 막는다.
- `backend/app/services/lostark_client.py`
  - 캐릭터 raw 응답은 저장하지만 경매장/옵션 raw 히스토리는 제한적이다.

즉 현재 구조는 **서비스 운영용 캐시**에는 적합하지만, **50GB 연구 데이터셋 축적용 구조는 아니다**.

## 3. 데이터 계층

50GB는 한 종류의 데이터로 채우지 않는다. 아래 4계층으로 나눈다.

### L0. Raw API Archive

원본 API 응답 보관 계층. 수정 금지, append-only.

- 캐릭터 Armory 응답
- `/auctions/options` 응답
- `/auctions/items` 응답
- `/markets/items` 응답
- `/markets/items/{itemId}` 응답
- `/markets/trades` 응답

포맷:

- `json.zst` 또는 `json.gz`
- 응답 본문 전체 저장
- 요청 payload, 수집 시각, endpoint, status code, 대상 캐릭터/아이템/쿼리 키를 함께 저장

### L1. Normalized Parquet

분석 가능한 정규화 테이블 계층. append-only.

- `character_snapshots`
- `equipment_items`
- `accessory_effects`
- `bracelet_effects`
- `ability_stones`
- `memory_inputs`
- `auction_accessory_candidates`
- `auction_accessory_matches`
- `auction_stone_candidates`
- `auction_stone_matches`
- `auction_bracelet_candidates`
- `auction_bracelet_matches`
- `auction_option_dictionary_snapshots`
- `material_price_snapshots`
- `market_trade_snapshots`

### L2. Curated DuckDB / Views

보고서, 집계, 통계용 계층.

- 최신 상태 대시보드
- 클래스별/서버별 분포
- 옵션 매칭 성공률
- 가격 분포 요약
- 실험 배치 단위 메타데이터

### L3. Simulation Experiment Store

50GB를 안정적으로 확보하는 핵심 계층. Monte Carlo 실험 row-level 저장.

- `simulation_batches`
- `simulation_rows`
- `simulation_quantiles`
- `simulation_scenarios`

이 계층은 “실제 유저 상태”를 입력으로 하되, 여러 `seed`, 가격 fingerprint, memory 힌트 조합, 모델 버전 조합을 돌린다.

## 4. 외부 데이터 루트

실데이터는 저장소 바깥에 둔다. 예시는 아래와 같다.

```text
E:\loa-hsi-data
```

권장 환경 변수:

```env
LOA_HSI_DATA_ROOT=E:\loa-hsi-data
LOA_HSI_RAW_ROOT=E:\loa-hsi-data\raw
LOA_HSI_PARQUET_ROOT=E:\loa-hsi-data\parquet
LOA_HSI_DUCKDB_PATH=E:\loa-hsi-data\db\loa_hsi.duckdb
LOA_HSI_EXPERIMENT_ROOT=E:\loa-hsi-data\experiments
```

저장소 내부 `data/`는 다음 용도로만 쓴다.

- 개발용 샘플
- 소규모 테스트
- 예시 결과

## 5. 권장 디렉터리 구조

```text
E:\loa-hsi-data
  raw
    armories
      date=YYYY-MM-DD
        hour=HH
          server=SERVER
            character=NAME
              20260616T101530Z_profiles.json.zst
              20260616T101531Z_equipment.json.zst
              20260616T101531Z_engravings.json.zst
              20260616T101531Z_arkpassive.json.zst
    auctions_options
      date=YYYY-MM-DD
        hour=HH
          20260616T100000Z_options.json.zst
    auctions_items
      date=YYYY-MM-DD
        hour=HH
          query_type=accessory_core_match
            part=necklace
              20260616T101540Z_req-<hash>.json.zst
          query_type=ability_stone_positive_pair
          query_type=bracelet_fixed_effects
    markets_items
      date=YYYY-MM-DD
        hour=HH
          material_key=<key>
            20260616T102000Z_req-<hash>.json.zst
    markets_trades
      date=YYYY-MM-DD
        hour=HH
          item_key=<key>
            20260616T102010Z_req-<hash>.json.zst
    manifests
      date=YYYY-MM-DD
        20260616T10_manifest.ndjson

  parquet
    character_snapshots
      date=YYYY-MM-DD
        hour=HH
          part-0001.parquet
    auction_accessory_candidates
      date=YYYY-MM-DD
        hour=HH
        server=SERVER
        class=CLASS
          part-0001.parquet
    auction_accessory_matches
    auction_stone_candidates
    auction_stone_matches
    auction_bracelet_candidates
    auction_bracelet_matches
    auction_option_dictionary_snapshots
    material_price_snapshots
    market_trade_snapshots

  db
    loa_hsi.duckdb

  experiments
    simulation_rows
      date=YYYY-MM-DD
        batch_id=<uuid>
          part-0001.parquet
    simulation_quantiles
    manifests
```

## 6. 수집 소스와 목적

### 6.1 캐릭터 Armory

소스:

- `/armories/characters/{name}/profiles`
- `/armories/characters/{name}/equipment`
- `/armories/characters/{name}/engravings`
- `/armories/characters/{name}/arkpassive`

목적:

- 캐릭터 현재 상태 복원
- 장비/장신구/스톤/팔찌 입력 생성
- 시뮬레이션 입력 fingerprint 생성

### 6.2 경매장 옵션 사전

소스:

- `/auctions/options`

목적:

- `ApiValue`/`Value` 기준 필터 코드 사전 보관
- 옵션명 변경 또는 응답 구조 변경 시점 추적
- 장신구/스톤/팔찌 검색 재현성 확보

이 응답은 **매일 최소 1회**, 가능하면 **6시간마다 1회** 스냅샷 보관한다.

### 6.3 장신구 경매장 검색

기준:

- `4티어 고대 / 핵심 옵션 / 품질 ±10 / 이름 무관 / 부위별`
- 응답 `Options`에서 핵심 옵션 직접 검증
- `BuyPrice=1`도 정상 인정
- 가격 하한 필터 없음

저장:

- 요청 payload raw
- 응답 raw
- 후보 매물 전체 row
- 검증 통과 row
- 검증 실패 사유

### 6.4 어빌리티 스톤 경매장 검색

기준:

- 같은 이름
- 같은 등급
- 같은 티어
- 같은 긍정 각인 2개
- 감소 각인 제외
- `BuyPrice=1`도 정상 인정

저장:

- 요청 payload raw
- 응답 raw
- 후보 매물 전체 row
- 긍정 각인 2개 매치 통과 row

### 6.5 팔찌 경매장 검색

기준:

- 현재 팔찌의 **고정 효과만** 기준
- 4티어 고대
- 랜덤 옵션 기대값은 별도 모델로 계산

저장:

- 요청 payload raw
- 응답 raw
- 후보 매물 전체 row
- 고정 효과 검증 통과 row
- 사용한 `/auctions/options` 해석 결과

### 6.6 재료/시장 가격

소스:

- `/markets/items`
- `/markets/items/{itemId}`
- 필요 시 `/markets/trades`

목적:

- 강화 비용 재현
- 시간대별 가격 변동 추적

## 7. 수집 작업 분리

서비스 API 호출과 연구용 배치 수집을 분리한다.

### A. 운영 경로

사용자가 웹에서 조회할 때 필요한 최소 저장만 수행한다.

- 최신 캐릭터 캐시
- 최신 가격 캐시
- 사용자 리포트 결과

### B. 연구 배치 경로

별도 배치 작업으로 대용량 수집한다.

- `collect_armory_snapshots`
- `collect_auction_options_snapshots`
- `collect_market_price_snapshots`
- `collect_accessory_auction_samples`
- `collect_stone_auction_samples`
- `collect_bracelet_auction_samples`
- `run_simulation_experiments`

이 경로는 append-only로 저장한다.

## 8. 권장 수집 주기

### 일일 기준

- `auctions/options`: 4회/일
- 재료 시세: 24회/일 또는 12회/일
- 캐릭터 스냅샷: 2회/일 또는 4회/일
- 장신구/스톤/팔찌 경매장 샘플: 2회/일

### 예시 배치

```text
00:00  auctions/options
00:10  material prices
01:00  armory snapshot batch A
01:30  accessory auction batch A
02:00  stone auction batch A
02:30  bracelet auction batch A
06:00  auctions/options
12:00  auctions/options + material prices + batch B
18:00  auctions/options + material prices + batch C
23:00  simulation experiment batch
```

## 9. 50GB 용량 구성안

50GB는 아래처럼 나누는 것이 가장 현실적이다.

### 권장 목표

- Raw API archive: 8GB
- Normalized Parquet: 10GB
- DuckDB/curated views/temp indexes: 2GB
- Simulation experiment rows: 30GB

합계:

- 약 50GB

### 이유

- 원본 API 응답만으로 50GB를 채우려면 호출량이 과도해진다.
- 이 프로젝트는 원본 수집만큼 **시뮬레이션 row-level 데이터**도 연구 가치가 높다.
- Monte Carlo 결과는 seed, 시나리오, 가격 상태를 바꾸어 재현 가능한 대용량 데이터를 만들 수 있다.

## 10. 시뮬레이션 계층 용량 산정

`simulation_rows`의 대략적인 row 크기를 80~160 bytes로 본다.

예시:

- 1 batch = 캐릭터 1,000명
- 각 캐릭터당 12 시나리오
- 각 시나리오당 100,000 row

계산:

```text
1,000 x 12 x 100,000 = 1,200,000,000 rows
```

이 규모는 매우 크므로 실제 운영은 아래처럼 나눈다.

### 현실적인 목표 배치

- 캐릭터 300명
- 시나리오 8개
- 시나리오당 30,000 row

```text
300 x 8 x 30,000 = 72,000,000 rows
```

이 정도면 Parquet 압축 기준으로 수 GB~수십 GB 범위 확보가 가능하다. 여기에 일자별 배치를 누적하면 30GB 이상을 만들 수 있다.

## 11. 시뮬레이션 시나리오 설계

시나리오는 임의 증량이 아니라 명시적인 실험 변수로 관리한다.

- `seed`
- `model_version`
- `material_price_fingerprint`
- `memory_hint_mode`
- `character_cache_mode`
- `auction_price_mode`
- `bracelet_random_option_mode`
- `stone_override_mode`

예시:

- `baseline_v60_26`
- `material_price_peak`
- `material_price_low`
- `memory_hints_empty`
- `memory_hints_user_entered`
- `bracelet_slots_observed`
- `bracelet_slots_normalized`

## 12. 저장 규칙

### Raw

- 수정 금지
- 삭제 금지
- 압축 저장
- 요청 payload와 응답 body를 분리하지 말고 함께 저장

### Parquet

- append-only
- 파티션 기준 명시
- 스키마 변경 시 `schema_version` 기록

### DuckDB

- 재생성 가능한 파생 계층으로 취급
- raw/parquet에서 다시 만들 수 있어야 한다

## 13. 메타데이터 요구사항

모든 raw/normalized row에 아래 필드를 남긴다.

- `collected_at`
- `date`
- `hour`
- `source_endpoint`
- `request_type`
- `request_hash`
- `response_status`
- `model_version`
- `server_name`
- `character_name` 또는 `query_key`
- `raw_path`
- `options_snapshot_path`

경매장 검증 관련 추가 필드:

- `desired_options_raw`
- `resolved_etc_options`
- `resolved_api_values`
- `listing_options_raw`
- `match_result`
- `reject_reason`

## 14. 품질 검증

수집 파이프라인은 아래 검사를 매 배치 후 수행한다.

- raw 파일 개수 > 0
- raw manifest와 실제 파일 수 일치
- Parquet row 수 > 0
- `/auctions/options` 스냅샷 존재 여부
- 장신구 match row에 핵심 옵션 직접 검증 필드 존재 여부
- 스톤 match row에 긍정 각인 2개 필드 존재 여부
- 팔찌 match row에 고정 효과 검증 필드 존재 여부
- `BuyPrice=1`이더라도 조건 일치 시 reject되지 않았는지 샘플 점검

## 15. 현재 코드에서 필요한 구조 변경

### 반드시 필요한 변경

1. `DatasetWriter`에 히스토리 보존 모드 추가

- 현재 `latest_per_character` 삭제 대신
- `mode=latest_only | append_history` 선택 가능하게 변경

2. 외부 데이터 루트 설정 추가

- `DATA_DIR` 하나만 쓰지 말고
- raw/parquet/db/experiments 루트를 분리 가능하게 변경

3. 경매장 raw 보존 확대

- 장신구/스톤/팔찌 검색 payload와 응답을 모두 raw archive에 저장

4. 시뮬레이션 실험 저장소 분리

- 운영 캐시용 `simulation_store`
- 연구 데이터셋용 `experiment_store`

5. raw 압축 저장

- JSON plain text 대신 `zstd` 또는 `gzip`

### 있으면 좋은 변경

6. manifest 파일 생성

- 배치 단위 NDJSON manifest

7. 데이터셋 스키마 버전 테이블

- DuckDB에 `dataset_versions`, `batch_runs` 추가

## 16. GitHub 반영 원칙

GitHub에는 아래만 올린다.

- 코드
- 샘플 raw 1~2개
- 샘플 Parquet 1~2개
- 데이터 파이프라인 문서
- 결과 스크린샷/예시

GitHub에 올리지 않는 것:

- 50GB 실데이터
- 개인 수집 결과 전체
- 장기간 누적 raw archive
- 대형 DuckDB 파일

## 17. 단계별 실행 계획

### Phase 1. 구조 분리

- 외부 데이터 루트 설정
- 운영 데이터와 연구 데이터 분리
- 히스토리 보존 모드 추가

### Phase 2. Raw archive 확대

- 경매장 raw payload/response 저장
- `/auctions/options` 스냅샷 저장
- manifest 생성

### Phase 3. 정규화 테이블 확장

- accessory/stone/bracelet candidate/match 테이블 추가
- reject reason 기록

### Phase 4. Simulation experiment store

- 배치 단위 실험 저장
- quantile 요약 테이블 생성
- 시나리오 메타데이터 저장

### Phase 5. 운영 자동화

- 스케줄러 또는 배치 스크립트
- 일별 품질 점검 리포트
- 용량 모니터링

## 18. 최종 판단 기준

이 프로젝트에서 “50GB 수집 성공”은 단순 용량이 아니라 아래 조건을 만족해야 한다.

- raw에서 파생 결과를 다시 재현할 수 있다
- `/auctions/options`와 실제 `Options` 검증 관계를 추적할 수 있다
- 장신구, 스톤, 팔찌 규칙이 현재 프로젝트 기준과 일치한다
- `BuyPrice=1` 정상 매물도 보존된다
- GitHub에는 대용량 데이터가 올라가지 않는다
- 사용자 리포트 결과를 연구용 데이터셋과 연결할 수 있다

이 기준을 만족하면, `LOA_HSI`는 단순 웹앱이 아니라 **실제 경매장/공식 확률표 기반 캐릭터 성장 비용 데이터 분석 시스템**으로 제출 가능하다.
