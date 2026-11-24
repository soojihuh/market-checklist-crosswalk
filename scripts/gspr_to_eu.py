#!/usr/bin/env python3
"""MDR Annex I 하위 항목 JSON(gspr_split.py 출력) -> data/checklists/EU.json

입력: gspr_split.py 가 영/국문 대역 PDF 텍스트에서 만든 units JSON
사용: python scripts/gspr_to_eu.py <units.json>
EU.json 은 이 스크립트의 결과물이며, 이후에는 JSON을 직접 편집해도 된다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "checklists" / "EU.json"

TOP = {
    1: ("General requirement — intended performance, safety and effectiveness", "일반 요구사항 — 의도된 성능, 안전·유효성"),
    2: ("Meaning of 'reduce risks as far as possible'", "'위험의 최대한 감소'의 의미"),
    3: ("Risk management system", "위험관리 시스템"),
    4: ("Risk control measures", "위험통제 조치"),
    5: ("Use error", "사용 오류"),
    6: ("Lifetime", "수명"),
    7: ("Transport and storage", "운송 및 보관"),
    8: ("Undesirable side-effects vs benefits", "부작용 대 이익"),
    9: ("Annex XVI devices", "Annex XVI 기기"),
    10: ("Chemical, physical and biological properties", "화학적·물리적·생물학적 특성"),
    11: ("Infection and microbial contamination", "감염 및 미생물 오염"),
    12: ("Medicinal substance / absorbed or dispersed substances", "의약물질 포함 / 체내 흡수·분산 물질 기기"),
    13: ("Materials of biological origin", "생물학적 기원 물질"),
    14: ("Construction and interaction with the environment", "구성 및 환경과의 상호작용"),
    15: ("Diagnostic or measuring function", "진단·측정 기능"),
    16: ("Protection against radiation", "방사선 방호"),
    17: ("Electronic programmable systems and software", "전자 프로그래머블 시스템·소프트웨어"),
    18: ("Active devices and connected devices", "능동 기기 및 연결 기기"),
    19: ("Active implantable devices", "능동 이식형 기기"),
    20: ("Mechanical and thermal risks", "기계적·열 위험"),
    21: ("Devices supplying energy or substances", "에너지·물질 공급 기기"),
    22: ("Devices for lay persons", "일반인 사용 기기"),
    23: ("Label and instructions for use", "라벨 및 사용설명서"),
}

BASE = {
    "1": ["p:general-safety", "p:intended-performance", "s:benefit-risk"],
    "2": ["p:risk-management", "s:benefit-risk"],
    "3": ["p:risk-management"],
    "4": ["p:risk-management", "s:labelling-ifu", "s:general-safety"],
    "5": ["p:lay-usability"],
    "6": ["p:lifetime"],
    "7": ["p:transport-storage"],
    "8": ["p:benefit-risk"],
    "9": [],
    "10.1": ["p:materials", "p:biocompatibility"],
    "10.2": ["p:materials", "s:infection-sterility"],
    "10.3": ["p:materials", "s:medicinal-substance"],
    "10.4": ["p:materials", "s:labelling-ifu"],
    "10.5": ["s:materials", "s:environment-construction"],
    "10.6": ["p:materials"],
    "11.1": ["p:infection-sterility"],
    "11.2": ["p:infection-sterility"],
    "11": ["p:infection-sterility", "s:labelling-ifu"],
    "12": ["p:medicinal-substance"],
    "13": ["p:biological-origin", "s:infection-sterility"],
    "14.1": ["p:systems-interconnection", "s:labelling-ifu"],
    "14.2": ["p:environment-construction"],
    "14.3": ["p:environment-construction", "s:electrical-mech-thermal"],
    "14.4": ["p:environment-construction", "s:lifetime"],
    "14.5": ["p:systems-interconnection"],
    "14.6": ["p:lay-usability"],
    "14.7": ["s:environment-construction", "s:labelling-ifu"],
    "15": ["p:measuring-diagnostic"],
    "16": ["p:radiation-protection"],
    "17.1": ["p:software", "s:intended-performance"],
    "17.2": ["p:software", "s:risk-management", "s:cybersecurity"],
    "17.3": ["p:software", "s:environment-construction"],
    "17.4": ["p:cybersecurity", "s:software"],
    "18.1": ["p:active-connected", "s:risk-management"],
    "18.2": ["p:active-connected"],
    "18.3": ["p:active-connected"],
    "18.4": ["p:active-connected", "s:measuring-diagnostic"],
    "18.5": ["p:emc"],
    "18.6": ["p:emc"],
    "18.7": ["p:electrical-mech-thermal"],
    "18.8": ["p:cybersecurity"],
    "19": ["p:implantable"],
    "20": ["p:electrical-mech-thermal"],
    "21": ["p:energy-substance-supply"],
    "22": ["p:lay-usability", "s:labelling-ifu"],
    "23.1": ["p:labelling-ifu"],
    "23.2": ["p:labelling-ifu"],
    "23.3": ["p:labelling-ifu", "s:infection-sterility"],
    "23.4": ["p:labelling-ifu"],
}

# leaf overrides (full path -> topics)
OVERRIDE = {
    "14.2(a)": ["p:environment-construction", "s:lay-usability"],
    "14.2(c)": ["p:environment-construction", "s:materials"],
    "14.2(e)": ["s:materials", "s:environment-construction"],
    "14.2(f)": ["p:environment-construction", "s:systems-interconnection"],
    "14.2(g)": ["p:environment-construction", "s:lifetime"],
    "16.1(b)": ["p:radiation-protection", "s:labelling-ifu"],
    "16.2(a)": ["p:radiation-protection", "s:measuring-diagnostic"],
    "16.4(b)": ["p:radiation-protection", "s:measuring-diagnostic"],
    "16.4(c)": ["p:radiation-protection", "s:measuring-diagnostic"],
    "16.4(d)": ["p:radiation-protection", "s:measuring-diagnostic"],
    "23.2(h)": ["p:labelling-ifu", "p:udi"],
}

OWNNOTE = {
    "9": "EU 고유(Annex XVI 제품). 치과 X-ray/SW와 직접 관련 낮음.",
}


def clause_of(path):
    return re.match(r"^\d+(?:\.\d+)*", path).group(0)


def base_topics(path):
    c = clause_of(path)
    while c:
        if c in BASE:
            return list(BASE[c])
        c = c.rsplit(".", 1)[0] if "." in c else ""
    return []


def has(tops, tid):
    return any(t.split(":", 1)[1] == tid for t in tops)


def topics_for(path, en):
    if path in OVERRIDE:
        tops = list(OVERRIDE[path])
    else:
        tops = base_topics(path)
    c = clause_of(path)
    low = en.lower()

    def add(tid, strength="s"):
        if not has(tops, tid):
            tops.append(f"{strength}:{tid}")

    if re.search(r"unauthori[sz]ed access|it security|information security", low):
        add("cybersecurity")
    if "electromagnetic" in low:
        add("emc")
    if "radiation" in low:
        add("radiation-protection")
    if re.search(r"clinical (benefit|performance|evaluation|investigation)", low):
        add("clinical-evidence")
    if re.search(r"\budi\b", low):
        add("udi")
    if "software" in low:
        add("software")
    if re.search(r"steril", low):
        add("infection-sterility")
    return tops


LEAD = re.compile(r"^(\([a-z]{1,2}\)|\d{1,2}(?:\.\d{1,2}){0,2}\.?)\s+")


def clean(text):
    """항목 번호가 본문 앞에 중복으로 붙은 경우 제거 (예: '(d) 재료 특성…')."""
    return LEAD.sub("", text.strip(), count=1)


def is_heading(u):
    en = u["en"]
    if u["kind"] != "num":
        return False
    if re.search(r"\b(shall|must|should)\b", en):
        return False
    if en.rstrip().endswith((".", ";", ":")):
        return False
    return len(en) < 260


def main(units_path):
    units = json.load(open(units_path, encoding="utf-8"))
    sections = []
    skipped = []
    for u in units:
        if is_heading(u):
            skipped.append(u["path"])
            continue
        path = u["path"]
        top = int(path.split(".")[0].split("(")[0])
        t_en, t_ko = TOP[top]
        rec = {
            "id": f"EU-GSPR-{path}",
            "ref": f"GSPR {path}",
            "titleEn": f"{t_en} · {path}",
            "titleKo": f"{t_ko} · {path}",
            "summaryEn": clean(u["en"]),
            "summaryKo": clean(u["ko"]),
            "topics": topics_for(path, u["en"]),
            "group": {"key": str(top), "en": f"{top}. {t_en}", "ko": f"{top}. {t_ko}", "hideTitle": True},
        }
        note = OWNNOTE.get(path)
        if clause_of(path).split(".")[0] == "19":
            note = "치과 영상기기 비해당"
        if note:
            rec["ownNote"] = note
        sections.append(rec)
    out = {
        "market": "EU",
        "name": {"en": "EU MDR 2017/745 (GSPR)", "ko": "EU MDR 2017/745 (GSPR)"},
        "role": "hub",
        "verification": "official",
        "titleNote": "사용자가 제공한 영/국문 대역 PDF('MDR GSPR.pdf', MDR 원문 108–195쪽 구간의 Annex I)를 숫자 조항·(a)–(ab) 소항목 단위로 분할(항목 %d개). 영문은 규정 본문이며 이전 세션에서 EUR-Lex 통합본(2026-01-01)으로 번호·구조를 확인한 것과 일치(23.1 (a)–(h), 23.2 (a)–(s), 23.3 (a)–(j), 23.4 (a)–(ab)). 국문은 파일에 포함된 번역으로 번역 출처는 미확인. PDF의 판본(개정 반영 여부)은 미확인 — EUR-Lex 통합본에서는 10.4.1(b), 10.4.2(c)가 Reg. (EU) 2025/2457로 개정됨. 소제목만 있는 항목(10, 10.4, 11 등)은 카드에서 제외했고, 제목은 '큰 항목 · 조항 번호'로 구성. 토픽은 조항 단위 기본 매핑에 키워드(IT 보안, 전자기, 방사선, 임상, UDI, 소프트웨어, 멸균)를 더한 초안이며 RA 검토 필요. Annex I에는 'clinical evaluation' 표현이 없음(임상평가는 Art. 61/Annex XIV)." % len(sections),
        "topicsFormat": "p:<topic> = primary, s:<topic> = secondary",
        "sections": sections,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"wrote {OUT} ({len(sections)} sections; skipped headings: {skipped})")


if __name__ == "__main__":
    main(sys.argv[1])
