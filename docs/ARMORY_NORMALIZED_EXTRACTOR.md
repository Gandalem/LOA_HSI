# Armory Normalized Extractor

## 목적

이 추출기는 `armory raw bundle`을 시뮬레이션/분석 입력용 정규화 데이터셋으로 변환한다.

입력은 최신 canonical 큐다.

- `D:\LOA-HSI\data\processed\loawa\loawa_seed_canonical.ndjson`

각 row의 `armoryRawPath`를 읽어서 현재 최신 캐릭터 상태만 정규화한다.

즉, raw 전체를 중복 스캔하지 않고 다음 흐름으로 동작한다.

1. canonical에서 `armory_ok` row 선택
2. 각 row의 `armoryRawPath` 로드
3. `CharacterSummary` 파싱
4. 직업 각인 preset 추정
5. character/accessory/stone/bracelet dataset 출력

## 출력

NDJSON:

- `D:\LOA-HSI\data\processed\armory_normalized\character_snapshots.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\accessory_items.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\accessory_effects.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\ability_stones.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\bracelet_items.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\bracelet_effects.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\errors.ndjson`
- `D:\LOA-HSI\data\processed\armory_normalized\normalization_summary.json`

Parquet:

- `D:\LOA-HSI\data\parquet\armory_normalized\character_snapshots.parquet`
- `D:\LOA-HSI\data\parquet\armory_normalized\accessory_items.parquet`
- `D:\LOA-HSI\data\parquet\armory_normalized\accessory_effects.parquet`
- `D:\LOA-HSI\data\parquet\armory_normalized\ability_stones.parquet`
- `D:\LOA-HSI\data\parquet\armory_normalized\bracelet_items.parquet`
- `D:\LOA-HSI\data\parquet\armory_normalized\bracelet_effects.parquet`

## 실행

백엔드 파서 의존성이 필요하다.

```powershell
cd D:\LOA-HSI
python -m pip install -r backend\requirements.txt
```

전체 최신 데이터셋 생성:

```powershell
cd D:\LOA-HSI
python tools\extract_armory_normalized_dataset.py
```

일부만 테스트:

```powershell
cd D:\LOA-HSI
python tools\extract_armory_normalized_dataset.py --limit 100
```

Parquet 없이 NDJSON만 생성:

```powershell
cd D:\LOA-HSI
python tools\extract_armory_normalized_dataset.py --skip-parquet
```

## 테이블 개요

`character_snapshots`

- 캐릭터 1명당 1행
- 서버, 직업, 평균 아이템 레벨, 경고, class preset 정보 포함

`accessory_items`

- 목걸이/귀걸이/반지 단위 1행
- 품질, 연마 단계, 깨달음 포인트, 효과 목록 포함

`accessory_effects`

- 장신구 효과 1개당 1행
- 이후 핵심 옵션 매칭/통계 계산에 바로 사용 가능

`ability_stones`

- 캐릭터당 스톤 1행
- 1/2 긍정 각인, 감소 각인, `stone_type` 포함

`bracelet_items`

- 팔찌 1개당 1행
- 정규화된 효과 목록 JSON 포함

`bracelet_effects`

- 팔찌 효과 1개당 1행
- 고정/유효 옵션 분석 입력으로 사용 가능

## 비고

- 현재 추출기는 “최신 상태 데이터셋” 용도다.
- 동일 캐릭터의 시계열 히스토리 분석은 별도 append-only extractor로 분리하는 편이 맞다.
