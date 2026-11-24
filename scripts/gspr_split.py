"""Split the bilingual MDR Annex I text (pypdf output) into leaf units.
usage: python gspr_split.py in.txt out.json
"""
import json, re, sys

src, dst = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().split("\n")

HANGUL = re.compile(r"[가-힣]")
NUM = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,2})\.?\s+(.*)$")
LET = re.compile(r"^\(([a-z]{1,2})\)\s*(.*)$")
ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]

SKIP = re.compile(r"^(MEDICAL DEVICE REGULATION|Page \d+ / \d+|=== PAGE|CHAPTER|제\d장|ANNEX|부속서|GENERAL REQUIREMENTS|일반 요구사항|REQUIREMENTS REGARDING|설계 및 제조 요구사항|정보 제공 요구사항|\s*$)")

# restrict to Annex I
start = next(i for i, l in enumerate(lines) if l.startswith("ANNEX I ") or l.strip() == "ANNEX I 부속서 1")
end = next(i for i, l in enumerate(lines) if i > start and l.startswith("ANNEX II"))
body = lines[start + 1:end]


def next_letter(l):
    if l is None:
        return "a"
    if len(l) == 1:
        return chr(ord(l) + 1) if l != "z" else "aa"
    # aa -> ab ...
    return l[0] + chr(ord(l[1]) + 1)


def split_mixed(text):
    """split a line that holds English + Korean into (en, ko)."""
    m = HANGUL.search(text)
    if not m:
        return text, ""
    i = m.start()
    # back up to start of the Korean segment: nearest preceding marker token or word start
    j = i
    mk = list(re.finditer(r"(\((?:[a-z]{1,2})\)|\d{1,2}(?:\.\d{1,2}){0,2}\.?)\s", text[:i + 1]))
    if mk and i - mk[-1].start() < 12:
        j = mk[-1].start()
    else:
        while j > 0 and text[j - 1] != " ":
            j -= 1
    return text[:j].strip(), text[j:].strip()


units = []
cur = None
clause = None
last_letter = None
roman_mode = False
last_roman = None


def new_unit(kind, marker, path, en, ko):
    global cur
    cur = {"kind": kind, "marker": marker, "path": path, "en": [en] if en else [], "ko": [ko] if ko else []}
    units.append(cur)


for raw in body:
    line = raw.rstrip()
    if SKIP.match(line):
        continue
    s = line.strip()
    has_ko = bool(HANGUL.search(s))
    mnum = NUM.match(s)
    mlet = LET.match(s)

    marker = None
    kind = None
    rest = None
    def plausible(mk):
        parts = [int(x) for x in mk.split(".")]
        if not (1 <= parts[0] <= 23):
            return False
        if clause is None:
            return len(parts) == 1 and parts[0] == 1
        cp = [int(x) for x in clause.split(".")]
        if len(parts) == 1:
            return parts[0] in (cp[0], cp[0] + 1)
        if parts[0] != cp[0]:
            return False
        if len(parts) == 2:
            return (len(cp) == 1 and parts[1] in (1,)) or (len(cp) >= 2 and parts[1] in (cp[1], cp[1] + 1)) or (len(cp) == 1 and parts[1] == 1)
        if len(parts) == 3:
            return len(cp) >= 2 and parts[1] == cp[1] and (len(cp) == 2 and parts[2] == 1 or len(cp) == 3 and parts[2] in (cp[2], cp[2] + 1))
        return False

    if mnum and not (mnum.group(1).count(".") == 0 and len(mnum.group(1)) > 2) and plausible(mnum.group(1)):
        marker, kind, rest = mnum.group(1), "num", mnum.group(2)
    elif mlet:
        marker, kind, rest = mlet.group(1), "let", mlet.group(2)

    if marker is not None:
        # Korean twin of the current unit?
        twin = cur is not None and cur["marker"] == marker and cur["kind"] == kind and cur["ko"] == [] and has_ko and not cur.get("closed_en") is False
        if kind == "num":
            twin = twin and cur["path"] == marker
        if twin or (cur is not None and cur["marker"] == marker and cur["kind"] == kind and has_ko and not cur["ko"] and (kind == "num" and cur["path"] == marker or kind == "let")):
            cur["ko"].append(rest if rest else "")
            continue
        en, ko = split_mixed(rest)
        if kind == "num":
            clause = marker
            last_letter = None
            roman_mode = False
            new_unit("num", marker, marker, en if not has_ko or en else "", ko)
            continue
        # letter-like marker
        if marker == next_letter(last_letter) and not re.match(r"^(and|or|to|of)\b", rest.strip()):
            last_letter = marker
            new_unit("let", marker, f"{clause}({marker})", en, ko)
            continue
        # not the expected next letter -> it is a wrapped line such as "(n) and (r) of Section 23.2;"
        marker = None

    # continuation line
    if cur is None:
        continue
    if HANGUL.search(s):
        en, ko = split_mixed(s)
        if en:
            cur["en"].append(en)
        cur["ko"].append(ko)
    else:
        cur["en"].append(s)

out = []
for u in units:
    out.append({
        "path": u["path"],
        "kind": u["kind"],
        "en": re.sub(r"\s+", " ", " ".join(u["en"])).strip(),
        "ko": re.sub(r"\s+", " ", " ".join(u["ko"])).strip(),
    })
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("units:", len(out))
paths = [o["path"] for o in out]
print("dups:", sorted({p for p in paths if paths.count(p) > 1})[:20])
print("no_ko:", [o["path"] for o in out if not o["ko"]][:30])
print("no_en:", [o["path"] for o in out if not o["en"]][:30])
