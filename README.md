# LOA-HSI v60.1

로스트아크 성장 억까 리포트 프로젝트입니다.

## v60.1 변경 요약

- 장신구/팔찌 비용을 운 판정과 분리해 `marketCost`로 표시합니다.
- 장신구 시장가 추정은 사용자가 확인한 실제 매물 가격대에 맞춰 낮게 보정했습니다.
- 팔찌 비용은 베이스 팔찌 가격과 팔찌 돌 가격 × 시도 수를 분리합니다.
- 직접 획득한 팔찌를 돌린 경우 기억 기반 실제 비용에서 베이스 팔찌 가격을 0G로 처리합니다.
- 팔찌 랜덤 옵션 기대값은 “유효 카테고리 하나 이상”이 아니라 필요한 카테고리 개수 기준으로 계산합니다.
- 기존 프론트가 읽는 `expectedValues.braceletT4`도 `officialBraceletT4.randomOptionBasis` 기준값으로 동기화합니다.
- 동일 서버/닉네임 캐릭터는 데이터셋 저장 시 최신 스냅샷만 남기도록 덮어쓰기 처리합니다.

## 검증된 v60.1 기준값 예시

`천지도사 / 아만` 리포트 기준 정상 확인값입니다.

```text
artifactPaths.modelVersion = v60.1-market-cost-calibrated
expectedValues.braceletT4.version = v60.1-legacy-synced-from-officialBraceletT4
expectedValues.officialBraceletT4.version = v60.1-bracelet-random-category-counts

팔찌 랜덤 옵션 필요 카테고리 = special 3개
팔찌 랜덤 옵션 성공확률 = 2.7%
팔찌 랜덤 옵션 기대 시도 수 = 37.037회

장신구 시장가 중앙값 합계 = 95,000G
팔찌 기억 기반 비용 = 100,000G
팔찌 기대 기준 비용 = 37,000G
시장 재현 비용 합계 = 195,000G
```

## 현재 계산 범위

- 캐릭터 정보: 로스트아크 공식 API의 캐릭터 프로필, 장비, 각인, 아크패시브 정보를 사용합니다.
- 장비 재련: 로컬 T4 재련표와 DB에 수집된 재료 시세를 사용합니다.
- 어빌리티 스톤: 현재 캐릭터의 스톤 활성 레벨을 성공 횟수 기준으로 변환한 뒤 기대 시도 수를 계산하고, 사용자가 기억하는 실제 시도 개수와 비교합니다.
- 장신구 공식 확률: 공식 확률표 데이터와 현재 장신구 옵션을 매칭하고, 중복 제외 보정 기반 기대 시도 수를 계산합니다.
- 장신구 시장가: 실제 거래소/경매장 API 연동 전까지 부위, 품질 구간, 핵심 옵션 수, 유효 옵션 수를 이용한 보수적 시장가 추정값을 사용합니다.
- 팔찌 T4: 구매 시 고정 옵션과 랜덤 옵션 슬롯이 섞여 있고 구매 후 계정 귀속되는 구조로 해석합니다. 억까 판정에는 사용자가 직접 돌린 랜덤 옵션 시도 수만 기대값과 비교합니다.
- 기억 기반 보조 판정: 프론트 브라우저 `localStorage`에만 저장하며, 서버의 사용자 공용 데이터로 저장하지 않습니다.
- 데이터셋: 사용자가 직접 조회/리포트 생성한 캐릭터만 로컬 데이터셋에 저장합니다. 외부 캐릭터 대량 수집은 포함하지 않습니다.

## 비용/운 분리 규칙

- 시장 재현 비용은 구매/재구매 비용으로 표시합니다.
- 운 판정은 장기백, 스톤 시도 수, 장신구 직접 연마 시도 수, 팔찌 랜덤 옵션 시도 수로 따로 봅니다.
- 구매한 장신구 가격은 운 점수에 직접 섞지 않습니다.
- 직접 연마한 장신구만 시도 수를 기대값과 비교해 기억 기반 보조 판정에 반영합니다.
- 팔찌는 베이스 가격과 돌 가격을 분리하고, 직접 획득 팔찌는 베이스 비용을 0G로 봅니다.

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

## v61 예정

- v54~v60.1에서 `index.html` 보조 스크립트로 붙인 팔찌 카드와 기억 저장 UI를 React 컴포넌트로 이관합니다.
- `ResultPanel.jsx`에 v60.1 시장가 카드를 정식 React 컴포넌트로 추가합니다.
- 기존 `modules.accessory` 비용 표시는 “구형 연마 확률 기반 참고값”으로 분리합니다.
- 팔찌 옵션 개별 수치 구간과 공식 옵션명을 더 세밀하게 분리합니다.
- 실제 거래소/경매장 API가 확인되면 장신구 유사 매물과 팔찌 돌 가격을 실매물 기반으로 교체합니다.

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
