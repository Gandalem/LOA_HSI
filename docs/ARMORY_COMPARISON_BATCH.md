# Armory Comparison Batch

`armory_normalized` Parquet를 입력으로 받아 기존 시장/시뮬레이션 서비스를 재사용해 append-only 비교 데이터셋을 만드는 배치입니다.

## 목적

- `data/parquet/armory_normalized/character_snapshots.parquet` 기준으로 캐릭터 목록을 읽습니다.
- 각 캐릭터의 `source_raw_path` 원본 armory bundle JSON을 다시 열어 현재 백엔드 파서를 그대로 사용합니다.
- 기존 서비스 로직을 그대로 재사용합니다.
  - 어빌리티 스톤 시장가: `build_ability_stone_market_summary`
  - 장신구 공식 확률표: `build_official_accessory_effect_summary`
  - 팔찌 공식 구조: `build_official_bracelet_t4_summary`
  - 장신구 시장가: `build_market_cost_summary`
  - 팔찌 고정 효과 시장가: `build_bracelet_fixed_market_summary`
  - 시뮬레이션: `SimulationEngine`, `SimulationStore`
- 결과는 append-only Parquet + DuckDB view로 저장됩니다.

## 실행

기본 실행:

```powershell
python tools/run_armory_comparison_batch.py
```

소량 테스트:

```powershell
python tools/run_armory_comparison_batch.py --limit 10 --simulation-count 2000
```

오프셋 배치:

```powershell
python tools/run_armory_comparison_batch.py --offset 200 --limit 50 --simulation-count 5000
```

특정 캐릭터만:

```powershell
python tools/run_armory_comparison_batch.py --character-name 천지도사 --simulation-count 5000
```

경매장 트래픽을 더 천천히 보내고 싶으면:

```powershell
python tools/run_armory_comparison_batch.py --limit 20 --request-interval-ms 800 --character-retries 3
```

## 주요 옵션

- `--input-parquet`: 입력 parquet 경로
- `--source-raw-column`: 원본 armory bundle 경로가 들어 있는 컬럼명. 기본값은 `source_raw_path`
- `--offset`, `--limit`: 배치 분할 실행용
- `--simulation-count`: 캐릭터별 Monte Carlo 샘플 수
- `--seed`: 시뮬레이션 시드
- `--modules`: `equipment,abilityStone,accessory`
- `--run-label`: 사람이 읽기 쉬운 실행 라벨
- `--sleep-ms`: 캐릭터 사이 대기 시간
- `--request-interval-ms`: Lost Ark API 요청 간 최소 간격
- `--retry-429-count`: 요청 단위 429 재시도 횟수
- `--retry-429-sleep-seconds`: 요청 단위 429 재시도 대기 시간
- `--character-retries`: 캐릭터 단위 429 재시도 횟수
- `--character-retry-sleep-seconds`: 캐릭터 재시도 전 대기 시간

## 경로 규칙

- 배치 스크립트는 `--data-dir` 값을 `DATA_DIR`로 강제 주입합니다.
- 따라서 append-only comparison parquet와 DuckDB view는 항상 배치 입력과 같은 data root 아래에 생성됩니다.
- 로컬 Windows 실행에서 `.env`에 `/app/data`가 들어 있어도 배치 실행 시에는 `--data-dir`이 우선합니다.

## 출력

Run summary JSON:

```text
data/processed/armory_comparison/<run_id>_summary.json
```

Append-only Parquet tables:

```text
data/parquet/comparison_runs/date=YYYY-MM-DD/<run_id>.parquet
data/parquet/character_comparisons/date=YYYY-MM-DD/<run_id>.parquet
data/parquet/module_summaries/date=YYYY-MM-DD/<run_id>.parquet
data/parquet/comparison_failures/date=YYYY-MM-DD/<run_id>.parquet
```

DuckDB views:

```text
v_comparison_runs
v_character_comparisons
v_module_summaries
v_comparison_failures
```

## 테이블 개요

`comparison_runs`
- 실행 메타데이터 1행
- 입력 parquet, 처리 건수, 실패 건수, 시뮬레이션 설정, 모델 버전 기록

`character_comparisons`
- 캐릭터당 1행
- 클래스 preset, 스톤 기대값, 장신구/팔찌 공식 분석 요약, 시장가 요약, JSON 근거 컬럼 포함

`module_summaries`
- 캐릭터 x 모듈 1행
- `equipment`, `abilityStone`, `accessory`, `total`
- `avg/p50/p75/p90/p95/p99/min/max/std` 저장

`comparison_failures`
- 원본 bundle 파싱 실패, API 호출 예외 등 배치 실패 행 저장

## 운영 권장

- 처음에는 `--limit 10` 수준으로 확인 후 점진적으로 키우는 편이 안전합니다.
- `simulation_count`가 높고 경매장 조회도 많기 때문에 한 번에 2241명을 전부 돌리면 오래 걸립니다.
- 장기 실행은 `offset/limit`로 나누어 append-only run을 여러 개 쌓는 방식이 좋습니다.
- 429가 잦으면 `--request-interval-ms 700~1000` 정도로 시작하는 편이 안전합니다.
