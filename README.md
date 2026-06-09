# LOA-HSI v48

로스트아크 성장 억까 리포트 프로젝트입니다.

## v48 변경 요약

- README와 내부 표시 버전을 v48 기준으로 정리했습니다.
- 아이템 레벨 숫자 파싱 오류를 수정한 현재 기준을 문서에 반영했습니다.
- non-root Docker 환경에서도 `/app/data` 권한 문제가 나지 않도록 `data-init` 단계를 사용합니다.
- 모바일 화면에서 장비/장신구 표를 카드형으로 볼 수 있도록 UI를 정리했습니다.
- 계산 근거와 세부 분석 영역은 핵심 수치가 먼저 보이도록 문구와 표시 밀도를 줄였습니다.

## 현재 계산 범위

- 캐릭터 정보: 로스트아크 공식 API의 캐릭터 프로필, 장비, 각인, 아크패시브 정보를 사용합니다.
- 장비 재련: 로컬 T4 재련표와 DB에 수집된 재료 시세를 사용합니다.
- 어빌리티 스톤: 표시 활성 레벨을 성공 횟수 기준으로 변환한 뒤 목표 성공 확률과 기대 시도 수를 계산합니다.
- 장신구/팔찌: 현재 효과를 파싱하고, 직접 연마/직접 돌림으로 입력한 시도 수만 억까/상쇄 단서에 반영합니다.
- 장신구 실제 거래가 기반 평가는 아직 별도 기능으로 분리 예정입니다.

## 실행

```powershell
docker compose down --remove-orphans

if (Test-Path .\data\cache) { Remove-Item .\data\cache\* -Recurse -Force }
if (Test-Path .\data\db\loa_hsi.duckdb) { Remove-Item .\data\db\loa_hsi.duckdb -Force }

docker compose up -d --build --force-recreate
```

## 환경 변수

`.env`에 로스트아크 API JWT를 넣어야 캐릭터 조회와 거래소 시세 수집이 동작합니다.

```env
LOSTARK_API_KEY=your_lostark_jwt
```
