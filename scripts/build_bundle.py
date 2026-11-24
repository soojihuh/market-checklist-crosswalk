#!/usr/bin/env python3
"""data/*.json -> data/bundle.js (window.CHECKLIST_DATA).

index.html은 file:// 로 열어도(SharePoint/인트라넷 정적 배포 포함) 동작하도록
JSON을 fetch하지 않고 이 번들 스크립트를 <script>로 읽는다.
소스(JSON)를 수정한 뒤에는 이 스크립트를 실행해 번들을 다시 만든다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MARKET_ORDER = ["EU", "CA", "AU", "HK", "ASEAN", "BR"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def expand_topics(codes):
    """['p:software','s:cybersecurity'] -> [{'id','strength'}]"""
    out = []
    for c in codes:
        kind, _, tid = c.partition(":")
        if kind not in ("p", "s") or not tid:
            raise ValueError(f"bad topic code: {c!r}")
        out.append({"id": tid, "strength": "primary" if kind == "p" else "secondary"})
    return out


AU_GROUPS = {
    "11": ("Protection against radiation", "방사선 방호"),
    "12": ("Medical devices connected to or equipped with an energy source", "에너지원에 연결·장착된 의료기기"),
    "13": ("Information to be provided with medical devices", "기기와 함께 제공할 정보"),
}
HK_GROUPS = {
    "7": ("Chemical, physical and biological properties", "화학·물리·생물학적 특성"),
    "8": ("Infection and microbial contamination", "감염·미생물 오염"),
    "9": ("Manufacturing and environmental properties", "제조·환경 특성"),
    "10": ("Devices with a diagnostic or measuring function", "진단·측정 기능"),
    "11": ("Protection against radiation", "방사선 방호"),
    "12": ("Devices connected to or equipped with an energy source", "에너지원 연결·장착 기기"),
    "13": ("Protection against mechanical risks", "기계적 위험 보호"),
    "14": ("Risks posed by supplied energy or substances", "에너지·물질 공급 위험"),
    "15": ("Self-testing or self-administration devices", "자가검사·자가투여 기기"),
    "16": ("Information supplied by the manufacturer", "제조자 제공 정보"),
    "17": ("Performance evaluation including clinical evaluation", "성능 평가(임상 평가 포함)"),
}
ASEAN_GROUPS = {
    "6.1": ("General principles", "일반 원칙"),
    "6.2.1": ("Chemical, physical and biological properties", "화학·물리·생물학적 특성"),
    "6.2.2": ("Infection and microbial contamination", "감염·미생물 오염"),
    "6.2.3": ("Manufacturing and environmental properties", "제조·환경 특성"),
    "6.2.4": ("Devices with a diagnostic or measuring function", "진단·측정 기능"),
    "6.2.5": ("Protection against radiation", "방사선 방호"),
    "6.2.6": ("Devices connected to or equipped with an energy source", "에너지원 연결·장착 기기"),
    "6.2.7": ("Protection against mechanical risks", "기계적 위험 보호"),
    "6.2.8": ("Supplied energy or substances", "에너지·물질 공급"),
    "6.2.9": ("Self-testing or self-administration devices", "자가검사·자가투여 기기"),
    "6.2.10": ("Information supplied by the manufacturer", "제조자 제공 정보"),
    "6.2.11": ("Performance evaluation including clinical evaluation", "성능 평가(임상 평가 포함)"),
}


def derive_group(market, s):
    """표 보기에서 하위 항목을 묶기 위한 큰 항목(group). 레코드에 group이 있으면 그대로 사용."""
    if s.get("group"):
        return s["group"]
    ref = s["ref"]
    if market == "AU":
        m = re.match(r"^EP (\d+[A-C]?)\.\d", ref)
        if m and m.group(1) in AU_GROUPS:
            en, ko = AU_GROUPS[m.group(1)]
            return {"key": "EP" + m.group(1), "en": f"EP {m.group(1)} — {en}", "ko": f"EP {m.group(1)} — {ko}"}
    elif market == "HK":
        m = re.match(r"^Clause (\d+)\.\d", ref)
        if m and m.group(1) in HK_GROUPS:
            en, ko = HK_GROUPS[m.group(1)]
            return {"key": "C" + m.group(1), "en": f"Clause {m.group(1)} — {en}", "ko": f"Clause {m.group(1)} — {ko}"}
    elif market == "ASEAN":
        m = re.match(r"^MDA/GD/0007 (6\.1|6\.2\.\d+)", ref)
        if m and m.group(1) in ASEAN_GROUPS:
            en, ko = ASEAN_GROUPS[m.group(1)]
            return {"key": m.group(1), "en": f"{m.group(1)} {en}", "ko": f"{m.group(1)} {ko}"}
    elif market == "CA":
        if re.match(r"^Section 16\([a-e]\)", ref):
            return {"key": "s16", "en": "Section 16 — Minimise risk from reasonably foreseeable hazards", "ko": "Section 16 — 예측 가능한 위험 최소화"}
    return None


def build():
    topics = load(DATA / "topics.json")["topics"]
    topic_ids = {t["id"] for t in topics}

    markets = {}
    for path in sorted((DATA / "checklists").glob("*.json")):
        m = load(path)
        default_ver = m.get("verification", "unverified")
        sections = []
        for s in m["sections"]:
            tp = expand_topics(s.get("topics", []))
            for t in tp:
                if t["id"] not in topic_ids:
                    raise ValueError(f"{s['id']}: unknown topic {t['id']}")
            sections.append({
                "id": s["id"],
                "market": m["market"],
                "ref": s["ref"],
                "titleEn": s["titleEn"],
                "titleKo": s["titleKo"],
                "summaryEn": s.get("summaryEn", ""),
                "summaryKo": s.get("summaryKo", ""),
                "topics": tp,
                "ownNote": s.get("ownNote", ""),
                "needsReview": s.get("needsReview", True),
                "verification": s.get("verification", default_ver),
                "group": derive_group(m["market"], s),
                "standards": s.get("standards", []),
            })
        ids = [s["id"] for s in sections]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate ids in {path.name}")
        markets[m["market"]] = {
            "market": m["market"],
            "name": m["name"],
            "role": m.get("role", "spoke"),
            "structure": m.get("structure", "checklist"),
            "verification": default_ver,
            "titleNote": m.get("titleNote", ""),
            "sections": sections,
        }

    ordered = [k for k in MARKET_ORDER if k in markets] + [k for k in markets if k not in MARKET_ORDER]
    bundle = {
        "topics": topics,
        "marketOrder": ordered,
        "markets": markets,
        "sources": load(DATA / "sources.json"),
        "changelog": load(DATA / "changelog.json"),
        "review": load(DATA / "review.json"),
    }
    out = DATA / "bundle.js"
    with open(out, "w", encoding="utf-8") as f:
        f.write("// 자동 생성 파일 — scripts/build_bundle.py 로 재생성. 직접 수정 금지.\n")
        f.write("window.CHECKLIST_DATA = ")
        json.dump(bundle, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    return out, sum(len(m["sections"]) for m in markets.values())


if __name__ == "__main__":
    try:
        out, n = build()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"wrote {out} ({n} sections)")
