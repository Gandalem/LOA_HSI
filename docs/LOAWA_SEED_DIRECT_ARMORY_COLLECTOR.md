# Seed Direct Armory Collector

## 목적

이 수집기는 `KLOA/LOAWA` seed를 별도 사전 검증 없이 바로 공식 Lost Ark API 본수집으로 넘긴다.

즉, 흐름은 다음과 같다.

1. seed canonical에서 캐릭터 이름을 읽는다.
2. 공식 API `profiles`, `equipment`, `engravings`, `arkpassive`를 직접 호출한다.
3. 성공하면 raw armory bundle을 저장한다.
4. 실패하면 canonical에 재시도 가능 여부만 남긴다.

이 방식은 `seed -> precheck -> 본수집`처럼 API를 두 번 치지 않아서 더 효율적이다.

## 관련 파일

- collector: `D:\LOA-HSI\tools\collect_seed_armory_bundle.mjs`
- 입력 큐: `D:\LOA-HSI\data\processed\loawa\loawa_seed_canonical.ndjson`
- 실행 스크립트: `npm run collect:armory`

## 수집 상태

canonical에는 `apiStatus`와 별도로 `armoryStatus`를 기록한다.

- `armory_ok`
- `armory_not_found`
- `armory_failed_retryable`
- `armory_failed_terminal`

별도 precheck를 생략해도 본수집 큐 상태는 이 값만으로 관리할 수 있다.

## 출력

- raw armory bundle:
  - `D:\LOA-HSI\data\raw\characters\*_armory_bundle_v1.json`
- local cache:
  - `D:\LOA-HSI\data\cache\character_*_armory_bundle_v1.json`
- batch log:
  - `D:\LOA-HSI\data\processed\loawa\seed_armory_collect_checks.ndjson`
- batch summary:
  - `D:\LOA-HSI\data\processed\loawa\seed_armory_last_batch_summary.json`

## 실행

기본 실행:

```powershell
cd D:\LOA-HSI\tools
node collect_seed_armory_bundle.mjs --limit 100 --sleep-ms 1200
```

또는:

```powershell
cd D:\LOA-HSI\tools
npm run collect:armory -- --limit 100 --sleep-ms 1200
```

중요:

- `--sleep-ms`는 seed 간 대기가 아니라 공식 API 요청 간 대기다.
- 캐릭터 1명 성공 시 보통 `profiles`, `equipment`, `engravings`, `arkpassive` 최대 4회 호출한다.
- 그래서 `429`를 피하려면 초반에는 `1200` 정도로 시작하는 게 안전하다.

## 재시도

초기 미수집 + 재시도 대상만 같이 돌리려면:

```powershell
cd D:\LOA-HSI\tools
node collect_seed_armory_bundle.mjs --status missing,armory_failed_retryable --limit 500 --sleep-ms 1200
```

재시도만 돌리려면:

```powershell
cd D:\LOA-HSI\tools
node collect_seed_armory_bundle.mjs --status armory_failed_retryable --limit 500 --sleep-ms 1500
```

강제로 다시 수집하려면:

```powershell
cd D:\LOA-HSI\tools
node collect_seed_armory_bundle.mjs --force --limit 100
```

## 권장 순서

1. 먼저 `--limit 50` 또는 `100`으로 테스트한다.
2. `429`가 없으면 `500`, `1000`으로 늘린다.
3. `armory_ok`가 누적되면 이후 장비/장신구/스톤/팔찌 분석 배치 입력으로 사용한다.

## 비고

- 기존 `verify_loawa_seeds_api.mjs`는 seed 존재 여부를 빠르게 확인하는 용도로는 여전히 쓸 수 있다.
- 하지만 대량 수집 기준 기본 경로는 이 direct armory collector를 쓰는 것이 맞다.
