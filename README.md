# LOA-HSI v54

로스트아크 성장 억까 리포트 프로젝트입니다.

## v54 변경 요약

- v53에서 추가한 `expectedValues.officialBraceletT4` 결과를 리포트 화면에 별도 카드로 표시합니다.
- 팔찌 T4 공식 구조 카드에서 등급, 도약 포인트, 평균 고정 효과 수, 평균 부여 효과 수를 보여줍니다.
- 현재 팔찌 효과의 공식 카테고리 매칭 성공/미분류/핵심 효과 수를 보여줍니다.
- 카테고리 기준 조합 확률, 기대 시도 수, 부여효과 수 충족 확률을 표시합니다.
- 팔찌 효과별 공식 카테고리, 역할 판정, 카테고리 표기확률을 카드 형태로 보여줍니다.
- 옵션 개별 수치 구간별 표기확률은 아직 미분리 상태임을 리포트 화면에 명시합니다.

## 현재 계산 범위

- 캐릭터 정보: 로스트아크 공식 API의 캐릭터 프로필, 장비, 각인, 아크패시브 정보를 사용합니다.
- 장비 재련: 로컬 T4 재련표와 DB에 수집된 재료 시세를 사용합니다.
- 어빌리티 스톤: 현재 캐릭터의 스톤 활성 레벨을 성공 횟수 기준으로 변환한 뒤 기대 시도 수를 계산하고, 사용자가 기억하는 실제 시도 개수와 비교합니다.
- 장신구 효과: 공식 확률표 데이터와 현재 장신구 옵션을 매칭하고, 중복 제외 보정 기반 기대 시도 수를 계산합니다.
- 팔찌 T4: 공식 효과 개수/카테고리 확률과 현재 팔찌 효과 카테고리를 매칭합니다. v54에서는 이 결과를 리포트 화면에 표시합니다.
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

## v55 예정

- 팔찌 공식 매칭 UI를 `index.html` 보조 스크립트에서 React 컴포넌트로 이관합니다.
- 팔찌 옵션 개별 수치 구간과 공식 옵션명을 더 세밀하게 분리합니다.
- 데이터셋 기반 직업/레벨대별 분포 비교 API를 준비합니다.
- 공식 기대값, 실제 저장 데이터 분포, 기억 입력을 합친 최종 억까 판정 백엔드 이관을 준비합니다.

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
