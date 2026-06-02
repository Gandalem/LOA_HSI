"""icepeng/loa-calc에서 재련/확률/재료 관련 후보 파일을 찾는 보조 스크립트.

이 스크립트는 값을 자동으로 100% 신뢰해서 가져오는 용도가 아니라,
과제에서 재련 필요 재료량/확률표를 검증할 때 참고할 후보 파일을 빠르게 찾기 위한 도구입니다.

실행:
    python tools/import_icepeng_candidates.py

출력:
    config/icepeng_candidates/manifest.json
    config/icepeng_candidates/*.ts 또는 *.json 후보 파일

주의:
    최종 보고서에는 실제 사용한 수치가 어떤 파일/버전에서 왔는지 반드시 기록하세요.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO = "icepeng/loa-calc"
BRANCH = "main"
OUT_DIR = Path("config/icepeng_candidates")
KEYWORDS = [
    "재련", "강화", "장인의", "기운", "확률", "성공", "파편", "돌파석", "융화", "수호", "파괴",
    "honing", "upgrade", "prob", "probability", "success", "material", "shard", "leapstone", "fusion",
]
TEXT_EXT = (".ts", ".json", ".js", ".html")


def fetch_json(url: str):
    req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "loa-hsi-starter"})
    with urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    req = Request(url, headers={"User-Agent": "loa-hsi-starter"})
    with urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def score_text(text: str) -> int:
    low = text.lower()
    score = 0
    for kw in KEYWORDS:
        score += low.count(kw.lower())
    # 수치표 가능성을 높게 평가
    score += len(re.findall(r"\b0\.\d+\b|\b\d+%", text))
    return score


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tree_url = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
    try:
        tree = fetch_json(tree_url)
    except (HTTPError, URLError, TimeoutError) as e:
        print(f"GitHub tree 조회 실패: {e}", file=sys.stderr)
        return 1

    candidates: List[Dict[str, object]] = []
    for node in tree.get("tree", []):
        path = node.get("path", "")
        if node.get("type") != "blob" or not path.endswith(TEXT_EXT):
            continue
        if not path.startswith("src/"):
            continue
        raw_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{path}"
        try:
            text = fetch_text(raw_url)
        except Exception:
            continue
        score = score_text(text)
        if score <= 0:
            continue
        safe_name = path.replace("/", "__")
        out_path = OUT_DIR / safe_name
        out_path.write_text(text, encoding="utf-8")
        candidates.append({
            "repo": REPO,
            "branch": BRANCH,
            "path": path,
            "raw_url": raw_url,
            "local_path": str(out_path),
            "score": score,
            "keyword_hits": {kw: text.lower().count(kw.lower()) for kw in KEYWORDS if text.lower().count(kw.lower()) > 0},
        })

    candidates.sort(key=lambda x: int(x["score"]), reverse=True)
    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(candidates[:50], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"후보 {len(candidates)}개 발견. 상위 50개 manifest 저장: {manifest_path}")
    for item in candidates[:10]:
        print(f"score={item['score']:>4} path={item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
