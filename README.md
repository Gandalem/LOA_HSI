# LOA-HSI API Starter

로스트아크 성장 스트레스 지수(LOA-HSI) 과제용 스타터입니다.

핵심 목표:

- 로스트아크 Open API로 재련 재료/장신구/스톤 가격 수집
- 유저가 직접 장신구/스톤 경매장 검색 조건을 드롭다운으로 설정
- 저장된 최신 가격을 Monte Carlo 시뮬레이터에 반영
- 평균 비용이 아니라 P90/P99 체감 불운 비용을 계산
- 골드 비용과 공식 과금 기준 원화 환산 비용을 함께 표시

## 실행

```bash
cp .env.example .env
# .env의 LOSTARK_API_KEY에 로스트아크 Open API JWT 입력

docker compose up -d --build
```

접속:

```text
http://localhost
```

## 이번 버전에서 추가된 것

### 1. 드롭다운 기반 장신구/스톤 경매장 검색

프론트 화면에 `장신구/스톤 경매장 검색` 패널이 추가되었습니다.

- payload JSON을 직접 입력하지 않습니다.
- `/api/options/auctions/parsed`로 경매장 옵션 코드를 조회한 뒤 드롭다운으로 선택합니다.
- 현재 장신구 기준에 맞춰 악세 검색 조건에서 `특성`, `유효각인`을 제거했습니다.
- 직업과 직업 각인은 장신구 검색 조건이 아니라 프리셋 추천과 결과 이름에만 사용합니다.
- 장신구 검색은 부위, 등급, 티어, 품질, 연마/아크 옵션, 깨달음 최소값 중심입니다.
- 어빌리티 스톤 검색은 스톤 각인 1, 스톤 각인 2를 사용합니다.
- 검색 결과 최저 즉시구매가를 `accessory_base` 또는 `ability_stone` 가격으로 저장할 수 있습니다.
- 저장된 가격은 `/api/prices/latest`에서 확인되고 시뮬레이션에 자동 반영됩니다.

관련 API:

```text
GET  /api/options/auctions
POST /api/auctions/search
POST /api/collect/auctions
GET  /api/prices/latest
```

### 2. pyLoa 사용 여부

`pyLoa`는 로스트아크 Open API 래퍼입니다. README 기준으로 `api.markets.search_items(...)`, `api.markets.get_item(...)`, `api.auctions.get_items(...)`, `api.auctions.get_options()` 같은 사용법을 제공합니다.

이 스타터는 Docker 배포 안정성을 위해 pyLoa를 필수 의존성으로 고정하지 않고 raw HTTP 클라이언트를 사용합니다. 대신 메서드 구조와 payload 흐름은 pyLoa와 유사하게 맞췄습니다. 나중에 pyLoa로 바꾸고 싶으면 `backend/app/services/lostark_client.py`만 교체하면 됩니다.

### 3. icepeng/loa-calc 데이터 후보 찾기

`icepeng/loa-calc`는 Angular 기반 계산기 프로젝트입니다. 재련 필요 재료량/확률 후보를 찾기 위한 보조 스크립트를 넣었습니다.

```bash
python tools/import_icepeng_candidates.py
```

출력:

```text
config/icepeng_candidates/manifest.json
config/icepeng_candidates/*.ts 또는 *.json
```

주의: 이 스크립트는 후보 파일을 찾는 도구입니다. 최종 과제에서는 실제 사용한 수치를 반드시 확인하고, `config/honing_rules.template.csv`를 복사해서 출처와 함께 정리하세요.

## 데이터 흐름

```text
드롭다운 조건 선택
→ 자동 payload 생성
→ POST /api/auctions/search
→ raw JSON 저장
→ 최저가/상위 N개 평균가 추출
→ latest_prices.json 저장
→ 시뮬레이터가 ability_stone/accessory_base 가격 사용
```

## 현재 남은 TODO

1. `/api/options/auctions/parsed` 결과에서 장신구/스톤 카테고리 코드 확인
2. 장신구 연마/깨달음 옵션 코드가 실제 검색 조건과 맞는지 확인
3. `tools/import_icepeng_candidates.py`로 icepeng 후보 파일 찾기
4. 재련 확률/재료량을 `simulator.py` 또는 별도 CSV 로더로 교체
5. 실제 수집 가격으로 10만 명 이상 시뮬레이션 실행

## 주의

- 비공식 현금거래 시세는 사용하지 마세요.
- 원화 환산은 공식 과금 기준으로 직접 입력한 `krw_per_gold`를 사용합니다.
- 장신구/스톤 조건은 유저마다 다르므로 이 프로젝트는 하드코딩 대신 유저 입력 방식을 사용합니다.

## v0.5 변경사항: 현재 장신구 구조 반영

이 버전부터 장신구 검색에서 구버전 조건을 제거했습니다.

제거된 조건:

```text
장신구 유효각인
장신구 특성
직업각인을 장신구 검색 조건으로 직접 넣는 방식
```

새 장신구 검색 흐름:

1. 웹 화면에서 `경매장 옵션 조회`를 먼저 누릅니다.
2. 검색 유형을 `장신구`로 선택합니다.
3. 직업과 직업각인은 프리셋 추천용으로만 고릅니다.
4. 실제 검색 조건은 부위, 등급, 티어, 품질, 연마 단계, 연마/아크 옵션, 깨달음 최소값을 사용합니다.
5. `자동 생성된 API payload 보기`에서 실제 요청 body를 확인할 수 있습니다.
6. `경매장 검색/가격 저장`을 누르면 최저가 또는 상위 N개 평균가가 `latest_prices.json`에 저장됩니다.

어빌리티 스톤 검색은 여전히 스톤 각인 1, 스톤 각인 2를 사용합니다.

주의: 로스트아크 공식 API의 옵션 코드는 `auctions/options` 응답을 기준으로 매칭됩니다. 옵션 조회 없이 검색하면 일부 세부 조건이 payload에 들어가지 않을 수 있습니다.
