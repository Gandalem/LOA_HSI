# LOA-HSI v55

로스트아크 성장 억까 리포트 프로젝트입니다.

## v55 변경 요약

- 팔찌 구매/귀속 구조를 반영해 고정 옵션과 랜덤 옵션 슬롯을 분리했습니다.
- 현재 팔찌 효과 전체 5개를 하나의 랜덤 목표로 계산하지 않도록 수정했습니다.
- 구매 당시 붙어 있던 고정 옵션은 사용자가 직접 돌린 운으로 보지 않고, 직접 돌린 랜덤 옵션 슬롯만 기대값 비교 대상으로 봅니다.
- `expectedValues.officialBraceletT4.randomOptionBasis`를 추가해 랜덤 옵션 기준 성공률과 기대 시도 수를 제공합니다.
- 리포트 화면의 팔찌 T4 공식 매칭 카드도 전체 조합 확률 대신 랜덤 옵션 기준 확률과 기대 시도 수를 표시합니다.
- 옵션 개별 수치 구간별 표기확률은 아직 미분리 상태이므로 카테고리 기준 확률로만 표시합니다.

## 현재 계산 범위

- 캐릭터 정보: 로스트아크 공식 API의 캐릭터 프로필, 장비, 각인, 아크패시브 정보를 사용합니다.
- 장비 재련: 로컬 T4 재련표와 DB에 수집된 재료 시세를 사용합니다.
- 어빌리티 스톤: 현재 캐릭터의 스톤 활성 레벨을 성공 횟수 기준으로 변환한 뒤 기대 시도 수를 계산하고, 사용자가 기억하는 실제 시도 개수와 비교합니다.
- 장신구 효과: 공식 확률표 데이터와 현재 장신구 옵션을 매칭하고, 중복 제외 보정 기반 기대 시도 수를 계산합니다.
- 팔찌 T4: 구매 시 고정 옵션과 랜덤 옵션 슬롯이 섞여 있고 구매 후 계정 귀속되는 구조로 해석합니다. 억까 판정에는 사용자가 직접 돌린 랜덤 옵션 시도 수만 기대값과 비교해야 합니다.
- 데이터셋: 사용자가 직접 조회/리포트 생성한 캐릭터만 로컬 데이터셋에 저장합니다. 외부 캐릭터 대량 수집은 포함하지 않습니다.

## 데이터 저장 경로

Docker 컨테이너 내부 경로와 Windows 호스트 경로는 다음처럼 매핑됩니다.

```text
/app/data/raw      -> D:\LOA-HSI\data\raw
/app/data/cache    -> D:\LOA-HSI\data\cache
/app/data/parquet  -> D:\LOA-HSI\data\parquet
/app/data/db       -> D:\LOA-HSI\data\db
```

Parquet 테이블 구조:

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
GET /api/dataset/stats
```

`status`는 저장 파일/행/용량/경로 확인용이고, `stats`는 앱 대시보드에 표시할 요약 통계용입니다.

## 공식 확률표 데이터

아래 공식 확률표를 로컬 JSON 데이터로 분리했습니다.

- `backend/config/accessory_polishing_probabilities_official.json`: 기존 계산기 호환용 장신구 공식 확률표 파일입니다.
- `backend/config/accessory_effect_probabilities_official.json`: 장신구 공식 효과 매칭 계산에 사용하는 데이터 뼈대입니다.
- `backend/config/bracelet_t4_probabilities_official.json`: 팔찌 T4 효과 수/카테고리/중복 제외 규칙 데이터 뼈대입니다.

## v56 예정

- 팔찌 공식 매칭 UI를 `index.html` 보조 스크립트에서 React 컴포넌트로 이관합니다.
- 팔찌 구매 당시 고정 옵션 수/직접 돌린 랜덤 슬롯 수를 사용자가 명시 입력할 수 있게 합니다.
- 팔찌 옵션 개별 수치 구간과 공식 옵션명을 더 세밀하게 분리합니다.
- 데이터셋 기반 직업/레벨대별 분포 비교 API를 준비합니다.

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
