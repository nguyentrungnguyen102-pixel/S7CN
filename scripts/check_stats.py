#!/usr/bin/env python3
"""Offline validator for the data blocks (M, PM, P, MG) embedded in
stats.html. No network access, no credentials required.

Usage:
    python3 scripts/check_stats.py [--html stats.html] [--xlsx <path>]

Exit code 0 only if all hard checks pass. Warnings never fail the run.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


# ---------------------------------------------------------------------------
# Extraction: pull `const NAME = <literal>;` text out of stats.html by
# bracket/brace depth scanning (robust against nested braces/brackets,
# unlike a plain regex over the whole statement).
# ---------------------------------------------------------------------------

def find_block(text, const_name):
    pattern = re.compile(r"^const " + re.escape(const_name) + r"\s*=", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        raise ValueError(f"const {const_name}= not found in html")
    open_pos = m.end()
    # skip whitespace to the opening bracket/brace
    while text[open_pos].isspace():
        open_pos += 1
    open_ch = text[open_pos]
    if open_ch == "[":
        close_ch = "]"
    elif open_ch == "{":
        close_ch = "}"
    else:
        raise ValueError(f"Unexpected literal opening for {const_name}: {open_ch!r}")

    depth = 0
    i = open_pos
    in_str = None
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ("'", '"'):
            in_str = ch
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[open_pos : i + 1]
        i += 1
    raise ValueError(f"Unterminated literal for {const_name}")


# ---------------------------------------------------------------------------
# Tolerant JS object-literal -> JSON conversion. The blocks use unquoted
# keys (both identifier-style and bare-numeric, e.g. MG's `21:{...}`) and
# bare-decimal numbers like `.55`. We quote keys and JSON-ify decimals,
# then hand off to json.loads. Callers must verify round-trip counts.
# ---------------------------------------------------------------------------

_KEY_WORD_RE = re.compile(r'([{,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)\s*:')
_KEY_NUM_RE = re.compile(r'([{,]\s*)(\d+)\s*:')
_BARE_DECIMAL_RE = re.compile(r'(:)(-?)\.(\d+)')
_TRAILING_COMMA_RE = re.compile(r',(\s*[\]}])')


def js_to_json(literal_text):
    s = literal_text
    s = _KEY_WORD_RE.sub(r'\1"\2":', s)
    s = _KEY_NUM_RE.sub(r'\1"\2":', s)
    s = _BARE_DECIMAL_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}0.{m.group(3)}', s)
    s = _TRAILING_COMMA_RE.sub(r'\1', s)
    return json.loads(s)


def parse_blocks(html_text):
    raw_M = find_block(html_text, "M")
    raw_MG = find_block(html_text, "MG")
    raw_P = find_block(html_text, "P")
    raw_PM = find_block(html_text, "PM")

    M = js_to_json(raw_M)
    MG_raw = js_to_json(raw_MG)
    MG = {int(k): v for k, v in MG_raw.items()}
    P = js_to_json(raw_P)
    PM = js_to_json(raw_PM)

    # Round-trip sanity: count entries in the raw text independently of
    # the parser and make sure the parsed structure agrees.
    raw_m_count = len(re.findall(r'\bwk\s*:', raw_M))
    assert raw_m_count == len(M), (
        f"M round-trip mismatch: {raw_m_count} 'wk:' occurrences in raw text "
        f"vs {len(M)} parsed entries"
    )
    raw_p_count = len(re.findall(r'\bn\s*:', raw_P))
    assert raw_p_count == len(P), (
        f"P round-trip mismatch: {raw_p_count} 'n:' occurrences in raw text "
        f"vs {len(P)} parsed entries"
    )
    raw_sc_count = len(re.findall(r'\bsc\s*:', raw_MG))
    parsed_sc_count = sum(len(v.get("s", [])) for v in MG.values())
    assert raw_sc_count == parsed_sc_count, (
        f"MG round-trip mismatch: {raw_sc_count} 'sc:' occurrences in raw text "
        f"vs {parsed_sc_count} parsed goal entries"
    )
    raw_gk_count = len(re.findall(r'\bgk\s*:', raw_MG))
    parsed_gk_count = sum(len(v.get("c", [])) for v in MG.values())
    assert raw_gk_count == parsed_gk_count, (
        f"MG round-trip mismatch: {raw_gk_count} 'gk:' occurrences in raw text "
        f"vs {parsed_gk_count} parsed conceded entries"
    )

    return M, MG, P, PM


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.hard_fail = False

    def check(self, name, ok, detail=""):
        status = PASS if ok else FAIL
        if not ok:
            self.hard_fail = True
        line = f"[{status}] {name}"
        if detail:
            line += f" - {detail}"
        print(line)

    def warn(self, name, detail=""):
        line = f"[{WARN}] {name}"
        if detail:
            line += f" - {detail}"
        print(line)


def run_checks(M, MG, P, PM, report):
    m_by_wk = {m["wk"]: m for m in M}
    p_names = {p["n"] for p in P}
    pm_names = set(PM.keys())

    # 1. every PM[name] has len == len(M)
    bad = [name for name, arr in PM.items() if len(arr) != len(M)]
    report.check(
        "1. len(PM[name]) == len(M) for every player",
        not bad,
        f"{len(bad)} mismatched: {bad[:10]}" if bad else f"all {len(PM)} arrays length {len(M)}",
    )

    # 2. every name in PM exists in P and vice versa
    missing_in_P = sorted(pm_names - p_names)
    missing_in_PM = sorted(p_names - pm_names)
    ok = not missing_in_P and not missing_in_PM
    report.check(
        "2. PM names <-> P names",
        ok,
        f"in PM not P: {missing_in_P}; in P not PM: {missing_in_PM}" if not ok else f"{len(p_names)} names match",
    )

    # 3. every sc/as/gk name in MG exists in P
    mg_names = set()
    for mg in MG.values():
        for g in mg.get("s", []):
            mg_names.add(g["sc"])
            if g.get("as"):
                mg_names.add(g["as"])
        for c in mg.get("c", []):
            mg_names.add(c["gk"])
    unknown = sorted(mg_names - p_names)
    report.check(
        "3. every sc/as/gk name in MG exists in P",
        not unknown,
        f"unknown names: {unknown}" if unknown else f"{len(mg_names)} distinct names all known",
    )

    # 4. for each week in MG: len(s) == M[w].gf and len(c) == M[w].ga
    bad4 = []
    for wk, mg in MG.items():
        m = m_by_wk.get(wk)
        if m is None:
            continue  # reported separately in check 5
        if len(mg.get("s", [])) != m["gf"]:
            bad4.append(f"wk{wk}: len(s)={len(mg.get('s', []))} != gf={m['gf']}")
        if len(mg.get("c", [])) != m["ga"]:
            bad4.append(f"wk{wk}: len(c)={len(mg.get('c', []))} != ga={m['ga']}")
    # MG and M đều sinh từ cùng một sheet, nên lệch ở đây nghĩa là SHEET tự mâu
    # thuẫn (thiếu/thừa một dòng sự kiện), không phải generator hỏng.
    # Đây là LỖI THẬT: các thẻ trên trang sẽ cộng ra hai con số khác nhau cho
    # cùng một đại lượng (ví dụ thẻ thủ môn ra 51 bàn thua còn tổng quan ra 50).
    # Sửa trong sheet 'Log tuần' rồi tải lại + chạy rebuild_data.py.
    report.check(
        "4. len(MG[w].s)==M[w].gf and len(MG[w].c)==M[w].ga",
        not bad4,
        ("; ".join(bad4) + "  -> sheet thiếu/thừa dòng sự kiện trong 'Log tuần'; "
         "tải lại sheet rồi chạy rebuild_data.py")
        if bad4 else f"all {len(MG)} weeks consistent",
    )

    # 5. every week key in MG exists in M
    missing_weeks = sorted(set(MG.keys()) - set(m_by_wk.keys()))
    report.check(
        "5. every MG week key exists in M",
        not missing_weeks,
        f"MG weeks not in M: {missing_weeks}" if missing_weeks else f"all {len(MG)} MG weeks present in M",
    )

    # 6. sum(PM) == sum(M.gf) -- WARNING only
    pm_sum = sum(v for arr in PM.values() for v in arr if v)
    m_gf_sum = sum(m["gf"] for m in M)
    delta = m_gf_sum - pm_sum
    if delta == 0:
        report.check("6. sum(PM) == sum(M.gf)", True, f"both {pm_sum}")
    else:
        report.check("6. sum(PM) == sum(M.gf)", True, f"WARNING only, see below")
        report.warn(
            "6. sum(PM) vs sum(M.gf) delta",
            f"sum(PM)={pm_sum}, sum(M.gf)={m_gf_sum}, delta={delta} "
            "(a goal scored by a player with no attributable attendance row, "
            "and/or a missing goal row in the sheet - not a script bug)",
        )

    # 7. recompute T from M
    m_n = len(M)
    w = sum(1 for m in M if m["r"] == "W")
    d = sum(1 for m in M if m["r"] == "D")
    l = sum(1 for m in M if m["r"] == "L")
    gf = sum(m["gf"] for m in M)
    ga = sum(m["ga"] for m in M)
    gd = gf - ga
    pts = w * 3 + d
    ppg = pts / m_n if m_n else 0
    print(
        "[INFO] 7. Recomputed T: "
        f"m={m_n} w={w} d={d} l={l} gf={gf} ga={ga} gd={gd} pts={pts} ppg={ppg:.2f}"
    )

    # 8. recompute per-player m/g/mp/wp/w/d/l/gf/ga/gd from PM+M
    week_order = [m["wk"] for m in M]
    r_by_wk = {m["wk"]: m["r"] for m in M}
    gf_by_wk = {m["wk"]: m["gf"] for m in M}
    ga_by_wk = {m["wk"]: m["ga"] for m in M}
    print("[INFO] 8. Per-player table (recomputed from PM+M):")
    header = f"{'name':<16}{'m':>4}{'g':>4}{'mp':>7}{'wp':>7}{'w':>4}{'d':>4}{'l':>4}{'gf':>5}{'ga':>5}{'gd':>5}"
    print(header)
    for p in P:
        name = p["n"]
        arr = PM.get(name)
        if arr is None:
            continue
        pw = pd = pl = pgf = pga = pg = 0
        pm_matches = 0
        for i, wk in enumerate(week_order):
            v = arr[i] if i < len(arr) else None
            if v is None:
                continue
            pm_matches += 1
            pg += v
            r = r_by_wk[wk]
            if r == "W":
                pw += 1
            elif r == "D":
                pd += 1
            elif r == "L":
                pl += 1
            pgf += gf_by_wk[wk]
            pga += ga_by_wk[wk]
        mp = pm_matches / m_n if m_n else 0
        wp = pw / pm_matches if pm_matches else 0
        pgd = pgf - pga
        print(
            f"{name:<16}{pm_matches:>4}{pg:>4}{mp:>7.2f}{wp:>7.3f}{pw:>4}{pd:>4}{pl:>4}{pgf:>5}{pga:>5}{pgd:>5}"
        )

    return


def run_xlsx_crosscheck(xlsx_path, M, MG, PM, report):
    import rebuild_data as rd

    xM, xPM, xP, xMG, x_implied = rd.build(xlsx_path)

    diffs = []

    # M
    xm_by_wk = {m["wk"]: m for m in xM}
    m_by_wk = {m["wk"]: m for m in M}
    all_wks = sorted(set(xm_by_wk) | set(m_by_wk))
    for wk in all_wks:
        a, b = m_by_wk.get(wk), xm_by_wk.get(wk)
        if a != b:
            diffs.append(f"M wk{wk}: html={a} xlsx={b}")

    # MG
    all_mg_wks = sorted(set(MG.keys()) | set(xMG.keys()))
    for wk in all_mg_wks:
        a, b = MG.get(wk), xMG.get(wk)
        if a != b:
            diffs.append(f"MG wk{wk}: html={a} xlsx={b}")

    # PM
    all_names = sorted(set(PM.keys()) | set(xPM.keys()))
    for name in all_names:
        a, b = PM.get(name), xPM.get(name)
        if a != b:
            diffs.append(f"PM[{name!r}]: html={a} xlsx={b}")

    if x_implied:
        for wk in sorted(x_implied):
            for name, role in x_implied[wk]:
                report.warn(
                    "implied attendance (xlsx)",
                    f"T{wk} {name} ({role}) thiếu dòng điểm danh",
                )

    report.check(
        "9. html blocks match xlsx (--xlsx cross-check)",
        not diffs,
        f"{len(diffs)} differences" if diffs else "no differences",
    )
    if diffs:
        for line in diffs[:50]:
            print(f"    {line}")
        if len(diffs) > 50:
            print(f"    ... and {len(diffs) - 50} more")
        if sum(1 for d in diffs if "'lv'" in d) == len(diffs):
            print(
                "    ^ toàn bộ khác biệt chỉ nằm ở link xem lại (lv). Nghĩa là file xlsx"
                " đang dùng CŨ hơn sheet thật, hoặc link trong cột O sheet 'Thống kê match'"
                " đã được dời sang tuần khác. Tải lại sheet rồi chạy lại — đừng ghi đè bằng"
                " --force nếu chưa đối chiếu."
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", default=str(REPO_ROOT / "stats.html"))
    ap.add_argument("--xlsx", default=None)
    args = ap.parse_args()

    html_text = Path(args.html).read_text(encoding="utf-8")
    M, MG, P, PM = parse_blocks(html_text)

    report = Report()
    run_checks(M, MG, P, PM, report)

    if args.xlsx:
        run_xlsx_crosscheck(args.xlsx, M, MG, PM, report)

    print()
    if report.hard_fail:
        print("RESULT: FAIL (see [FAIL] lines above)")
        sys.exit(1)
    else:
        print("RESULT: PASS (warnings, if any, do not fail the run)")
        sys.exit(0)


if __name__ == "__main__":
    main()
