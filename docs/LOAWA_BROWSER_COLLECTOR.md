# Browser Seed Collector

## 목적

이 수집기는 랭킹 사이트에서 캐릭터 이름 seed를 최대한 많이 모으기 위한 브라우저 기반 수집기다.

현재 기본 소스는 `KLOA` 전투력 랭킹이다.

- 시작 URL: `https://kloa.gg/ranking/combat-power`
- 수집 기준: 랭킹 목록의 캐릭터 링크
- 확장 방식: `더 보기` 버튼을 누를 때마다 약 100명씩 추가 로딩

중요한 점:

- 여기서는 이름 seed만 확보한다.
- 실제 캐릭터 상세 데이터는 이후 공식 Lost Ark API로 다시 검증한다.
- raw HTML과 seed index를 같이 남겨서, 추후 selector 보정이나 중복 검사를 할 수 있게 한다.

## 관련 파일

- 수집기: `D:\LOA-HSI\tools\collect_loawa_seeds.mjs`
- 설정 예시: `D:\LOA-HSI\config\loawa_seed_queries.example.json`
- 출력 디렉터리:
  - `D:\LOA-HSI\data\raw\loawa\...`
  - `D:\LOA-HSI\data\processed\loawa\loawa_seed_index.ndjson`
  - `D:\LOA-HSI\data\processed\loawa\loawa_seed_canonical.ndjson`

## 사전 준비

```powershell
cd D:\LOA-HSI\tools
npm.cmd install
```

Chrome 또는 Edge가 설치되어 있어야 한다.

## 실행

기본 실행:

```powershell
cd D:\LOA-HSI\tools
node collect_loawa_seeds.mjs --source kloa_combat_power --max-pages 20
```

동작 방식:

1. 브라우저가 열린다.
2. 필요하면 로그인/보안 확인을 직접 처리한다.
3. 랭킹 페이지가 준비되면 Enter를 누른다.
4. collector가 현재 보이는 캐릭터 링크를 추출한다.
5. `더 보기` 버튼을 찾아 누르고, 다시 새로 늘어난 목록에서 추가 이름만 저장한다.

`--max-pages`는 페이지 번호가 아니라 배치 횟수다.

- `1`이면 첫 화면만 저장
- `20`이면 첫 화면 + `더 보기` 반복까지 최대 20회 배치 저장

즉, KLOA 기준으로 `--max-pages 20`이면 대략 2,000명 전후 seed를 기대할 수 있다.

더 많이 모으려면:

```powershell
cd D:\LOA-HSI\tools
node collect_loawa_seeds.mjs --source kloa_combat_power --max-pages 100
```

## 로그 해석

예상 로그 형태:

```text
[LOAWA] Target: kloa_combat_power -> https://kloa.gg/ranking/combat-power
[LOAWA] kloa_combat_power batch 1: 100 cumulative candidates
[LOAWA] kloa_combat_power batch 1: +100 new seeds
[LOAWA] kloa_combat_power batch 2: 200 cumulative candidates
[LOAWA] kloa_combat_power batch 2: +100 new seeds
```

여기서 중요한 값은 두 개다.

- `cumulative candidates`: 현재 화면까지 보이는 전체 후보 수
- `+N new seeds`: 이번 배치에서 실제로 새로 저장된 이름 수

## 권장 수집 순서

1. `--max-pages 20` 정도로 먼저 테스트한다.
2. `loawa_seed_index.ndjson`에 이름이 정상적으로 쌓이는지 확인한다.
3. 문제가 없으면 `--max-pages 100` 이상으로 늘린다.
4. 충분히 seed가 쌓이면 공식 API 검증 배치로 넘긴다.

## 주의

- KLOA 구조가 바뀌면 `nameSelectors` 또는 `loadMoreSelectors`를 조정해야 한다.
- 현재 canonical dedupe는 `characterName + href` 기준으로 먼저 모으고, 이후 API 검증 단계에서 실제 서버/대표 캐릭터 여부를 정리한다.
- GitHub에는 대용량 raw/processed 결과를 올리지 않는다.
