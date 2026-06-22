# LOAWA seed -> 공식 Lost Ark API 검증 배치

## 목적

이 배치는 `LOAWA`에서 모은 캐릭터 seed를 공식 Lost Ark API로 검증한다.

검증 결과:

- `api_ok`
- `api_not_found`
- `api_failed_retryable`
- `api_failed_terminal`

을 canonical seed에 기록하고, 성공 시 raw 캐릭터 bundle도 저장한다.

## 파일

- 검증기: `tools/verify_loawa_seeds_api.mjs`

## 입력

기본 입력:

- `data/processed/loawa/loawa_seed_canonical.ndjson`

이 파일은 브라우저 기반 `LOAWA` 수집기 실행 후 생성된다.

## 출력

- canonical 업데이트:
  - `data/processed/loawa/loawa_seed_canonical.ndjson`
- 검증 로그:
  - `data/processed/loawa/seed_api_checks.ndjson`
- 배치 요약:
  - `data/processed/loawa/seed_api_last_batch_summary.json`
- 공식 API raw:
  - `data/raw/characters/..._seed_verify_v1.json`
- 공식 API cache:
  - `data/cache/character_<name>_seed_verify_v1.json`

## 실행 전제

`.env` 또는 환경 변수에 `LOSTARK_API_KEY`가 있어야 한다.

예시:

```env
LOSTARK_API_KEY=your_lostark_open_api_jwt
```

## 실행

기본 실행:

```powershell
cd D:\LOA-HSI\tools
node verify_loawa_seeds_api.mjs --limit 100
```

특정 상태만 재검증:

```powershell
cd D:\LOA-HSI\tools
node verify_loawa_seeds_api.mjs --status api_failed_retryable --limit 50
```

강제 재검증:

```powershell
cd D:\LOA-HSI\tools
node verify_loawa_seeds_api.mjs --force --limit 200
```

캐시 무시:

```powershell
cd D:\LOA-HSI\tools
node verify_loawa_seeds_api.mjs --no-cache --limit 100
```

## 동작

1. canonical seed에서 대상 row를 선택한다.
2. 공식 API `profiles`, `equipment`, `engravings`, `arkpassive`를 조회한다.
3. 성공 시 `api_ok`로 기록하고 raw/cache 파일을 저장한다.
4. 실패 시 HTTP 상태에 따라 분류한다.
5. canonical row에 최신 서버/직업/아이템레벨 메타데이터를 갱신한다.

## 기본 상태 필터

기본적으로 아래 상태만 대상으로 잡는다.

- `discovered`
- `queued_for_api`
- `api_failed_retryable`

이미 `api_ok`인 row는 `--force` 없이 다시 조회하지 않는다.

## 다음 단계

이 배치 다음에는 아래가 이어져야 한다.

1. `api_ok` 캐릭터만 분리한 snapshot batch
2. 장신구/스톤/팔찌 비용 계산 배치
3. 시뮬레이션 실험 저장
