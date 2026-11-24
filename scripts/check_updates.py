#!/usr/bin/env python3
"""월간 출처 점검: data/sources.json 의 'auto' 출처를 조회해 변경을 감지한다.

- 표준 라이브러리만 사용 (GitHub Actions / 사내 PC 어디서나 실행 가능).
- 버전 필드(versionFields 정규식) 비교 = 신뢰도 높음, 본문 해시 비교 = 신뢰도 낮음(광고·날짜 등 노이즈 가능).
- 차단(401/403/429)·DNS 실패·타임아웃 출처는 우회하지 않고 '수동 확인 목록'으로 분리한다.
- 변경이 있으면 data/changelog.json 에 기록하고 reports/latest.md, reports/YYYY-MM.md 요약을 쓴다.
- 마지막에 data/bundle.js 를 재생성한다 (--no-bundle 로 생략).

사용: py -3 scripts/check_updates.py [--dry-run] [--no-bundle]
"""
import argparse
import hashlib
import html
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORTS = ROOT / "reports"
UA = "checklist-crosswalk-monitor/1.0 (internal regulatory-affairs monitoring; monthly)"
TIMEOUT = 45
BLOCK_CODES = {401, 403, 429}


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_text(url):
    """returns (status, text_or_reason). status: ok | blocked | error"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(8_000_000)
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype and "json" not in ctype:
                return "error", f"non-text content-type: {ctype}"
            charset = r.headers.get_content_charset() or "utf-8"
            return "ok", raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        return ("blocked" if e.code in BLOCK_CODES else "error"), f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return "error", f"URL error: {e.reason}"
    except (socket.timeout, TimeoutError):
        return "error", "timeout"
    except Exception as e:  # noqa: BLE001
        return "error", f"{type(e).__name__}: {e}"


def normalize(markup):
    t = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", markup)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def extract_fields(text, fields):
    out = {}
    for f in fields:
        m = re.search(f["regex"], text)
        out[f["name"]] = m.group(1) if m else None
    return out


def check_source(src, today):
    """returns result dict; mutates src only for lastChecked/lastStatus/hash/fields"""
    res = {"id": src["id"], "title": src["titleKo"], "market": src["market"], "kind": "ok", "detail": ""}
    status, payload = fetch_text(src["url"])
    src["lastChecked"] = today
    if status != "ok":
        src["lastStatus"] = f"{status}: {payload}"
        res["kind"] = "manual"
        res["detail"] = f"자동 조회 불가 ({payload}) — 수동 확인 목록으로 분리 (우회하지 않음)"
        return res

    text = normalize(payload)
    new_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    fields = extract_fields(text, src.get("versionFields", []))
    old_fields = src.get("lastFieldValues")
    old_hash = src.get("contentHash")

    src["lastStatus"] = "ok"
    misses = [k for k, v in fields.items() if v is None]
    if misses:
        res["detail"] = f"pattern-miss: {', '.join(misses)} (정규식이 페이지와 맞는지 확인 필요). "

    if old_hash is None and old_fields is None:
        res["kind"] = "baseline"
        res["detail"] += "첫 실행: 해시·버전 필드 기준선 기록."
    else:
        field_changes = []
        if old_fields:
            for k, v in fields.items():
                if v is not None and old_fields.get(k) not in (None, v):
                    field_changes.append(f"{k}: {old_fields.get(k)} → {v}")
        if field_changes:
            res["kind"] = "changed"
            res["detail"] += "버전 필드 변경 — " + "; ".join(field_changes)
        elif old_hash and old_hash != new_hash:
            res["kind"] = "content-changed"
            res["detail"] += "본문 해시 변경(신뢰도 낮음 — 광고·날짜 등 노이즈 가능, 수동 확인 권장)"
        else:
            res["kind"] = "unchanged"

    # 기준선 갱신
    src["contentHash"] = new_hash
    merged = dict(old_fields or {})
    merged.update({k: v for k, v in fields.items() if v is not None})
    src["lastFieldValues"] = merged
    if res["kind"] in ("changed",) and merged and not misses:
        src["lastKnownVersion"] = "; ".join(f"{k}={v}" for k, v in merged.items())
        src["lastKnownDate"] = today
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 출력")
    ap.add_argument("--no-bundle", action="store_true", help="bundle.js 재생성 생략")
    args = ap.parse_args()

    today = date.today().isoformat()
    sources = load(DATA / "sources.json")
    changelog = load(DATA / "changelog.json")

    results, manual = [], []
    for src in sources["sources"]:
        if src.get("checkMethod") == "manual" or not src.get("url"):
            src["lastStatus"] = "manual"
            manual.append(src)
            continue
        results.append(check_source(src, today))

    for r in results:
        if r["kind"] == "manual":
            src = next(s for s in sources["sources"] if s["id"] == r["id"])
            manual.append(src)

    changed = [r for r in results if r["kind"] in ("changed", "content-changed")]
    for r in changed:
        src = next(s for s in sources["sources"] if s["id"] == r["id"])
        changelog["entries"].append({
            "date": today,
            "sourceId": r["id"],
            "type": r["kind"],
            "summaryKo": r["detail"],
            "summaryEn": "Change detected by monthly check (see Korean summary).",
            "affectedSections": [f"{m} 시장 섹션 전체 점검" for m in src.get("affects", [])],
        })

    # 리포트
    lines = [f"# 월간 출처 점검 리포트 — {today}", ""]
    lines.append(f"- 자동 점검 {len(results)}건, 변경 감지 {len(changed)}건, 수동 확인 {len(manual)}건")
    lines.append("")
    lines.append("## 자동 점검 결과")
    for r in results:
        lines.append(f"- [{r['kind']}] {r['market']} · {r['title']}" + (f" — {r['detail']}" if r["detail"] else ""))
    lines.append("")
    lines.append("## 수동 확인 목록 (이번 달에 사람이 확인)")
    for s in manual:
        reason = s.get("manualReason") or s.get("lastStatus", "")
        lines.append(f"- {s['market']} · {s['titleKo']} — 현재 기준: {s.get('lastKnownVersion', '-')} / 사유: {reason}")
    lines.append("")
    lines.append("> 자동 감지는 참고용입니다. 변경이 의심되면 공식 원문에서 직접 확인하고 data/checklists/*.json 을 갱신하세요.")
    report = "\n".join(lines) + "\n"
    print(report)

    if args.dry_run:
        return 0

    save(DATA / "sources.json", sources)
    save(DATA / "changelog.json", changelog)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "latest.md").write_text(report, encoding="utf-8")
    (REPORTS / f"{today[:7]}.md").write_text(report, encoding="utf-8")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"changes_detected={'true' if changed else 'false'}\n")

    if not args.no_bundle:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import build_bundle  # noqa: PLC0415
        out, n = build_bundle.build()
        print(f"bundle: {out} ({n} sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
