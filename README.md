# LOA-HSI v51

로스트아크 성장 억까 리포트 프로젝트입니다.

## v51 변경 요약

- 리포트 생성 시 캐릭터/장비/장신구/팔찌/스톤/기억 입력을 로컬 Parquet 데이터셋으로 저장합니다.
- 저장된 데이터는 Docker 내부 기준 `/app/data/parquet`, Windows 기본 실행 기준 `D:\LOA-HSI\data\parquet` 아래에 쌓입니다.
- DuckDB에 `v_character_snapshots`, `v_equipment_items`, `v_accessory_effects`, `v_bracelet_effects`, `v_ability_stones`, `v_memory_inputs` 뷰를 자동 생성합니다.
- `/api/dataset/status` API로 Parquet 파일 수, 행 수, 용량, 경로를 확인할 수 있습니다.
- 프론트에서 입력한 기억 기반 보조 판정값을 백엔드로 함께 보내 데이터셋에 저장합니다.

## 현재 계산 범위

- 캐릭터 정보: 로스트아크 공식 API의 캐릭터 프로필, 장비, 각인, 아크패시브 정보를 사용합니다.
- 장비 재련: 로컬 T4 재련표와 DB에 수집된 재료 시세를 사용합니다.
- 어빌리티 스톤: 현재 캐릭터의 스톤 활성 레벨을 성공 횟수 기준으로 변환한 뒤 기대 시도 수를 계산하고, 사용자가 기억하는 실제 시도 개수와 비교합니다.
- 장신구 효과: 공식 확률표 데이터와 현재 장신구 옵션을 매칭하고, 중복 제외 보정 기반 기대 시도 수를 계산합니다.
- 팔찌: 현재 효과를 파싱하고, 직접 돌림으로 입력한 시도 수를 기존 보조 판정에 반영합니다. 공식 옵션명/등급 구간 직접 매칭은 후속 버전 예정입니다.
- 데이터셋: 사용자가 직접 조회/리포트 생성한 캐릭터만 로컬 데이터셋에 저장합니다. 외부 캐릭터 대량 수집은 포함하지 않습니다.

## 데이터 저장 경로

Docker 컨테이너 내부 경로와 Windows 호스트 경로는 다음처럼 매핑됩니다.

```text
/app/data/raw      -> D:\LOA-HSI\data\raw
/app/data/cache    -> D:\LOA-HSI\data\cache
/app/data/parquet  -> D:\LOA-HSI\data\parquet
/app/data/db       -> D:\LOA-HSI\data\db
```

v51 Parquet 테이블 구조:

```text
D:\LOA-HSI\data\parquet\character_snapshots\date=YYYY-MM-DD\*.parquet
D:\LOA-HSI\data\parquet\equipment_items\date=YYYY-MM-DD\*.parquet
D:\LOA-HSI\data\parquet\accessory_effects\date=YYYY-MM-DD\*.parquet
D:\LOA-HSI\data\parquet\bracelet_effects\date=YYYY-MM-DD\*.parquet
D:\LOA-HSI\data\parquet\ability_stones\date=YYYY-MM-DD\*.parquet
D:\LOA-HSI\data\parquet\memory_inputs\date=YYYY-MM-DD\*.parquet
```

## Dataset API

```text
GET /api/dataset/status
```

응답에는 각 테이블의 파일 수, 행 수, 크기, Parquet 경로가 포함됩니다.

## 공식 확률표 데이터

아래 공식 확률표를 로컬 JSON 데이터로 분리했습니다.

- `backend/config/accessory_polishing_probabilities_official.json`: 기존 계산기 호환용 장신구 공식 확률표 파일입니다.
- `backend/config/accessory_effect_probabilities_official.json`: 장신구 공식 효과 매칭 계산에 사용하는 데이터 뼈대입니다.
- `backend/config/bracelet_t4_probabilities_official.json`: 팔찌 T4 효과 수/카테고리/중복 제외 규칙 데이터 뼈대입니다.

## v52 예정

- 팔찌 T4 현재 옵션을 공식 옵션명/카테고리/등급 구간과 직접 매칭합니다.
- 팔찌 고정 효과/부여 효과/카테고리 확률과 중복 제외 보정을 실제 계산에 연결합니다.
- 데이터셋 기반 직업/레벨대별 분포 비교 API를 준비합니다.
- 장신구 공식 매칭 결과를 프론트 리포트 UI에 더 명확하게 표시합니다.

## 실행

```powershell
docker compose down --remove-orphans

docker compose up -d --build --force-recreate
```

## 환경 변수

`.env`에 로스트아크 API JWT를 넣어야 캐릭터 조회와 거래소 시세 수집이 동작합니다.

```env
LOSTARK_API_KEY=your_lostark_jwt
```
