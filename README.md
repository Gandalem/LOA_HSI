# LOA-HSI v46

로스트아크 성장 억까 리포트 프로젝트입니다.

## v46 변경 요약

- 팔찌 입력을 실제 구조에 맞게 정리했습니다.
- 팔찌는 완성품 구매가 아니라 베이스 팔찌 구매/직접 획득 후 랜덤 옵션을 직접 돌리는 방식으로 처리합니다.
- 팔찌 획득 방식에 `기억 안 남`, `베이스 팔찌 구매 후 직접 돌림`, `직접 획득한 팔찌를 돌림`을 추가했습니다.
- 직접 돌린 팔찌만 시도 수를 입력받아 기대 시도 수와 비교합니다.
- 팔찌 시도 수가 기대보다 많으면 억까 단서, 기대보다 적으면 상쇄 단서로 반영합니다.

## 실행

```powershell
docker compose down --remove-orphans

if (Test-Path .\data\cache) { Remove-Item .\data\cache\* -Recurse -Force }
if (Test-Path .\data\db\loa_hsi.duckdb) { Remove-Item .\data\db\loa_hsi.duckdb -Force }

docker compose up -d --build --force-recreate
```
