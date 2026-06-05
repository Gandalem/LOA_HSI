"""icepeng/loa-calc에서 재련 관련 후보 파일을 찾는 보조 스크립트입니다.

주의:
- 이 스크립트는 후보 파일을 찾는 용도입니다.
- 실제 프로젝트에 반영하기 전 라이선스, 최신성, 값의 의미를 직접 검증하세요.
- GitHub API 제한을 피하려면 로컬에서 repo를 clone한 뒤 grep으로 찾는 방식도 권장합니다.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "config" / "icepeng_candidates"
OUT.mkdir(parents=True, exist_ok=True)

KEYWORDS = ["honing", "upgrade", "success", "rate", "material", "재련", "확률", "강화", "장인의"]


def run(cmd: list[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT)


def main() -> None:
    work = ROOT / ".tmp_icepeng_loa_calc"
    if not work.exists():
        run(["git", "clone", "--depth", "1", "https://github.com/icepeng/loa-calc.git", str(work)])

    candidates = []
    for path in work.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".ts", ".js", ".json", ".html"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hit = [kw for kw in KEYWORDS if kw.lower() in text.lower()]
        if hit:
            rel = path.relative_to(work)
            dest = OUT / str(rel).replace("/", "__")
            dest.write_text(text, encoding="utf-8")
            candidates.append({"path": str(rel), "keywords": hit, "saved_as": str(dest.relative_to(ROOT))})

    manifest = OUT / "manifest.json"
    manifest.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(candidates)} candidates to {manifest}")


if __name__ == "__main__":
    main()
