# LOA-HSI v45

로스트아크 성장 억까 리포트 프로젝트입니다.

## v45 변경 요약

- 계산 근거 영역을 표 중심에서 카드형으로 정리했습니다.
- 가로 스크롤이 생기던 계산 근거 표를 모바일 친화 레이아웃으로 수정했습니다.
- 640px 이하 모바일 화면에서 카드, 입력창, 버튼, 결과 요약이 한 열로 자연스럽게 배치되도록 CSS를 보강했습니다.

## 실행

```powershell
docker compose down --remove-orphans

if (Test-Path .\data\cache) { Remove-Item .\data\cache\* -Recurse -Force }
if (Test-Path .\data\db\loa_hsi.duckdb) { Remove-Item .\data\db\loa_hsi.duckdb -Force }

docker compose up -d --build --force-recreate
```
