#!/usr/bin/env python3
"""
update_stats.py — Đọc dữ liệu LAIRAI FC từ Google Sheet và cập nhật stats.html.

Yêu cầu: Google Sheet phải được chia sẻ "Anyone with the link can view".
"""

import csv
import io
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ─── Config ───────────────────────────────────────────────────────────────────
SHEET_ID = "1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68"
GID      = "602325894"
HTML_FILE = Path(__file__).resolve().parent.parent / "stats.html"

# ─── Fetch ────────────────────────────────────────────────────────────────────
def fetch_sheet_rows() -> list:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={GID}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"✗ HTTP {e.code}: Google Sheet không truy cập được", file=sys.stderr)
        if e.code in (401, 403):
            print("  → Chia sẻ sheet: File → Share → Anyone with the link → Viewer", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Lỗi kết nối: {e}", file=sys.stderr)
        sys.exit(1)

    if text.strip().startswith("<"):
        print("✗ Sheet trả về HTML (có thể chưa public)", file=sys.stderr)
        print("  → Chia sẻ sheet: File → Share → Anyone with the link → Viewer", file=sys.stderr)
        sys.exit(1)

    return list(csv.reader(io.StringIO(text)))

# ─── Helpers ──────────────────────────────────────────────────────────────────
def find_header(rows: list, *keywords) -> int:
    """Trả về index của hàng đầu tiên chứa TẤT CẢ keywords."""
    for i, row in enumerate(rows):
        joined = " ".join(row)
        if all(k in joined for k in keywords):
            return i
    return -1

def cell(row: list, idx: int, default: str = "") -> str:
    return row[idx].strip() if idx < len(row) else default

def to_int(s: str) -> int:
    try:
        return int(float(s.replace(",", ".")))
    except (ValueError, TypeError):
        return 0

def pct_float(s: str) -> float:
    try:
        return round(float(s.replace("%", "").replace(",", ".")) / 100, 4)
    except (ValueError, TypeError):
        return 0.0

def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)

# ─── Parse: matches ───────────────────────────────────────────────────────────
def parse_matches(rows: list) -> list:
    idx = find_header(rows, "Tên Sân", "Đối thủ", "Kết quả")
    if idx == -1:
        idx = find_header(rows, "Đối thủ", "Bàn Thắng")
    if idx == -1:
        print("⚠  Không tìm thấy bảng lịch thi đấu", file=sys.stderr)
        return []

    hdr = rows[idx]
    c_ven  = next((i for i, h in enumerate(hdr) if "Tên Sân" in h), 4)
    c_opp  = next((i for i, h in enumerate(hdr) if "Đối thủ" in h), 5)
    c_gf   = next((i for i, h in enumerate(hdr) if "Thắng" in h and "Bàn" in h and "%" not in h), 7)
    c_ga   = next((i for i, h in enumerate(hdr) if "thua" in h and "Bàn" in h), 9)
    c_res  = next((i for i, h in enumerate(hdr) if "Kết quả" in h), 10)

    matches = []
    for row in rows[idx + 1:]:
        if not row:
            continue
        wk_str = cell(row, 0)
        if not wk_str.startswith("Tuần"):
            continue
        m = re.search(r"\d+", wk_str)
        if not m:
            continue
        wk = int(m.group())

        res_str = cell(row, c_res)
        if res_str not in ("Thắng", "Hòa", "Thua"):
            continue  # bỏ qua tuần nghỉ / chưa đấu

        try:
            gf = int(float(cell(row, c_gf)))
            ga = int(float(cell(row, c_ga)))
        except ValueError:
            continue

        r   = "W" if res_str == "Thắng" else "D" if res_str == "Hòa" else "L"
        dt  = cell(row, 1)[:5]   # "04/01"
        ven = cell(row, c_ven)
        opp = cell(row, c_opp)

        matches.append({"wk": wk, "dt": dt, "vs": opp, "gf": gf, "ga": ga, "r": r, "v": ven})

    matches.sort(key=lambda x: x["wk"])
    return matches

# ─── Parse: players ───────────────────────────────────────────────────────────
def parse_players(rows: list, match_weeks: list) -> tuple:
    idx = find_header(rows, "Biệt danh", "Vị trí", "Goals", "Match")
    if idx == -1:
        print("⚠  Không tìm thấy bảng cầu thủ", file=sys.stderr)
        return [], {}

    hdr = rows[idx]

    def col(*keywords):
        for i, h in enumerate(hdr):
            if all(k in h for k in keywords):
                return i
        return -1

    c_tt   = 0
    c_nick = col("Biệt danh")
    c_pos  = col("Vị trí")
    c_no   = col("Số áo")
    c_g    = next((i for i, h in enumerate(hdr) if h.strip() == "Goals"), -1)
    c_m    = next((i for i, h in enumerate(hdr) if h.strip() == "Match"), -1)
    c_mpct = col("%Match")
    c_wpct = next((i for i, h in enumerate(hdr) if "Win" in h and "%" in h), -1)
    c_w    = next((i for i, h in enumerate(hdr) if h.strip() == "Thắng"), -1)
    c_d    = next((i for i, h in enumerate(hdr) if h.strip() in ("Hòa", "Hoà")), -1)
    c_l    = next((i for i, h in enumerate(hdr) if h.strip() == "Thua"), -1)
    c_gf   = next((i for i, h in enumerate(hdr) if h.strip() == "GF"), -1)
    c_ga   = next((i for i, h in enumerate(hdr) if h.strip() == "GA"), -1)
    c_gd   = next((i for i, h in enumerate(hdr) if h.strip() == "GD"), -1)

    # Cột tuần: Tuần 52, Tuần 51, ..., Tuần 1
    weekly = {}
    for i, h in enumerate(hdr):
        wm = re.match(r"Tuần (\d+)$", h.strip())
        if wm:
            weekly[int(wm.group(1))] = i

    players, pm = [], {}

    for row in rows[idx + 1:]:
        if not row or c_nick < 0 or c_nick >= len(row):
            continue
        nick = cell(row, c_nick)
        if not nick:
            continue
        if any(k in nick for k in ("Biệt danh", "Tên Sân", "Họ và tên", "Nhóm")):
            break

        pos = cell(row, c_pos) if c_pos >= 0 else ""
        no  = cell(row, c_no)  if c_no  >= 0 else ""
        g   = to_int(cell(row, c_g))   if c_g  >= 0 else 0
        m   = to_int(cell(row, c_m))   if c_m  >= 0 else 0

        if m == 0 and g == 0 and not pos:
            continue

        mp = pct_float(cell(row, c_mpct)) if c_mpct >= 0 else (m / len(match_weeks) if match_weeks else 0)
        wp = pct_float(cell(row, c_wpct)) if c_wpct >= 0 else 0.0
        w  = to_int(cell(row, c_w))  if c_w  >= 0 else 0
        d  = to_int(cell(row, c_d))  if c_d  >= 0 else 0
        l  = to_int(cell(row, c_l))  if c_l  >= 0 else 0
        gf = to_int(cell(row, c_gf)) if c_gf >= 0 else 0
        ga = to_int(cell(row, c_ga)) if c_ga >= 0 else 0
        gd = to_int(cell(row, c_gd)) if c_gd >= 0 else 0

        tt = cell(row, c_tt)
        t  = "sub" if (not tt or tt.upper() == "SUB") else "main"

        players.append({
            "n": nick, "p": pos, "no": no,
            "g": g, "m": m, "mp": mp, "wp": wp,
            "fa": [],   # điền sau
            "w": w, "d": d, "l": l,
            "gf": gf, "ga": ga, "gd": gd,
            "t": t,
        })

        # Mảng bàn thắng theo từng trận (theo thứ tự M)
        if weekly and match_weeks:
            pm_row = []
            for wk in match_weeks:
                ci = weekly.get(wk, -1)
                if ci < 0:
                    pm_row.append(None)
                    continue
                val = cell(row, ci).upper()
                if val in ("FALSE", ""):
                    pm_row.append(None)
                elif val == "TRUE":
                    pm_row.append(0)
                else:
                    try:
                        pm_row.append(int(float(val)))
                    except ValueError:
                        pm_row.append(0)
            pm[nick] = pm_row

    return players, pm

def fill_form(players: list, pm: dict, results: list, n: int):
    """Tính phong độ 5 trận gần nhất cho từng cầu thủ."""
    start = max(0, n - 5)
    last_res = results[start:]
    for p in players:
        p_pm = pm.get(p["n"], [])
        fa = []
        for i, res in enumerate(last_res):
            abs_i = start + i
            played = abs_i < len(p_pm) and p_pm[abs_i] is not None
            fa.append(res if played else "N")
        p["fa"] = fa

# ─── Parse: goal details ──────────────────────────────────────────────────────
def parse_goal_details(rows: list) -> dict:
    idx = find_header(rows, "Hiệp", "Assist", "Loại bàn thắng")
    if idx == -1:
        idx = find_header(rows, "Hiệp", "Assist")
    if idx == -1:
        return {}

    hdr   = rows[idx]
    c_wk  = next((i for i, h in enumerate(hdr) if "Tuần" in h), 0)
    c_h   = next((i for i, h in enumerate(hdr) if "Hiệp" in h), 1)
    c_sc  = 2   # cột 3rd = scorer
    c_as  = next((i for i, h in enumerate(hdr) if "Assist" in h), 3)
    c_ty  = next((i for i, h in enumerate(hdr) if "Loại" in h), 4)

    mg = {}
    for row in rows[idx + 1:]:
        if not row:
            continue
        wk_str = cell(row, c_wk)
        sc     = cell(row, c_sc)
        if not wk_str or not sc:
            continue
        m = re.search(r"\d+", wk_str)
        if not m:
            continue
        wk    = int(m.group())
        h     = 2 if "2" in cell(row, c_h) else 1
        asst  = cell(row, c_as)
        gtype = cell(row, c_ty)

        if wk not in mg:
            mg[wk] = {"s": [], "ms": [], "pf": 0, "ps": 0}

        if "Hỏng" in gtype:
            mg[wk]["ms"].append({"sc": sc, "h": h})
        else:
            t = "pen" if "Pen" in gtype else "normal"
            e = {"sc": sc, "t": t, "h": h}
            if asst:
                e["as"] = asst
            mg[wk]["s"].append(e)

    # Xoá ms rỗng
    for v in list(mg.values()):
        if not v["ms"]:
            del v["ms"]

    return mg

# ─── JS serialisation ─────────────────────────────────────────────────────────
def team_js(matches: list) -> str:
    n  = len(matches)
    gf = sum(x["gf"] for x in matches)
    ga = sum(x["ga"] for x in matches)
    gd = gf - ga
    w  = sum(1 for x in matches if x["r"] == "W")
    d  = sum(1 for x in matches if x["r"] == "D")
    l  = sum(1 for x in matches if x["r"] == "L")
    form = json.dumps([x["r"] for x in matches[-5:]], ensure_ascii=False)
    return (
        f"const T={{m:{n},gf:{gf},ga:{ga},gd:{gd},w:{w},d:{d},l:{l},form:{form}}};\n"
        "T.pts=T.w*3+T.d; T.ppg=T.pts/T.m;"
    )

def matches_js(matches: list) -> str:
    parts = [
        f"  {{wk:{m['wk']},dt:{q(m['dt'])},vs:{q(m['vs'])}"
        f",gf:{m['gf']},ga:{m['ga']},r:{q(m['r'])},v:{q(m['v'])}}}"
        for m in matches
    ]
    return "const M=[\n" + ",\n".join(parts) + "\n];"

def players_js(players: list) -> str:
    parts = []
    for p in players:
        fa = json.dumps(p["fa"], ensure_ascii=False)
        parts.append(
            f'  {{n:{q(p["n"])},p:{q(p["p"])}'
            f',no:{q(p["no"])},g:{p["g"]},m:{p["m"]}'
            f',mp:{p["mp"]},wp:{p["wp"]},fa:{fa}'
            f',w:{p["w"]},d:{p["d"]},l:{p["l"]}'
            f',gf:{p["gf"]},ga:{p["ga"]},gd:{p["gd"]}'
            f',t:{q(p["t"])}}}'
        )
    return "const P=[\n" + ",\n".join(parts) + "\n];"

def pm_js(pm: dict) -> str:
    parts = [
        f'  {q(name)}:[{",".join("null" if g is None else str(g) for g in goals)}]'
        for name, goals in pm.items()
    ]
    return "const PM={\n" + ",\n".join(parts) + "\n};"

def mg_js(mg: dict) -> str:
    parts = []
    for wk in sorted(mg):
        d = mg[wk]
        scored = []
        for g in d.get("s", []):
            e = f'{{sc:{q(g["sc"])}'
            if "as" in g:
                e += f',as:{q(g["as"])}'
            e += f',t:{q(g["t"])},h:{g["h"]}}}'
            scored.append(e)
        missed = [f'{{sc:{q(g["sc"])},h:{g["h"]}}}' for g in d.get("ms", [])]
        conc   = [f'{{gk:{q(c["gk"])},h:{c["h"]}}}' for c in d.get("c", [])]
        ep = []
        if scored: ep.append(f's:[{",".join(scored)}]')
        if missed: ep.append(f'ms:[{",".join(missed)}]')
        if conc:   ep.append(f'c:[{",".join(conc)}]')
        ep += [f'pf:{d.get("pf",0)}', f'ps:{d.get("ps",0)}']
        parts.append(f"  {wk}:{{{','.join(ep)}}}")
    return "const MG={\n" + ",\n".join(parts) + "\n};"

# ─── Update HTML ──────────────────────────────────────────────────────────────
def update_html(matches: list, players: list, pm: dict, mg: dict):
    content = HTML_FILE.read_text(encoding="utf-8")
    n = len(matches)

    def sub(pattern, replacement, flags=re.DOTALL):
        nonlocal content
        content = re.sub(pattern, replacement, content, flags=flags)

    # T (team aggregate) — single line
    sub(
        r"const T=\{.*?\};\nT\.pts=T\.w\*3\+T\.d; T\.ppg=T\.pts/T\.m;",
        team_js(matches),
    )

    # M (matches array)
    sub(r"const M=\[.*?\];", matches_js(matches))

    # MG (goal details)
    sub(r"const MG=\{.*?\};", mg_js(mg))

    # P (players)
    sub(r"const P=\[.*?\];", players_js(players))

    # PM (per-match goals)
    if pm:
        sub(r"const PM=\{.*?\};", pm_js(pm))

    # Subtitle
    today = datetime.now().strftime("%d/%m/%Y")
    content = re.sub(
        r"Cập nhật sau \d+ trận.*?·",
        f"Cập nhật sau {n} trận &nbsp;·&nbsp; {today} &nbsp;·",
        content,
    )

    HTML_FILE.write_text(content, encoding="utf-8")
    print(f"✓ stats.html đã cập nhật ({n} trận, {len(players)} cầu thủ)")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("📥 Đang đọc Google Sheet …")
    rows = fetch_sheet_rows()
    print(f"   {len(rows)} dòng dữ liệu")

    print("📋 Phân tích trận đấu …")
    matches = parse_matches(rows)
    if not matches:
        print("✗ Không có trận nào, dừng lại.", file=sys.stderr)
        sys.exit(1)
    wks = [m["wk"] for m in matches]
    print(f"   {len(matches)} trận: Tuần {wks[0]} → {wks[-1]}")

    print("👥 Phân tích cầu thủ …")
    players, pm = parse_players(rows, wks)
    print(f"   {len(players)} cầu thủ")

    fill_form(players, pm, [m["r"] for m in matches], len(matches))

    print("⚽ Phân tích chi tiết bàn thắng …")
    mg = parse_goal_details(rows)
    print(f"   Tuần có dữ liệu: {sorted(mg) or 'chưa có'}")

    print("✏️  Cập nhật stats.html …")
    update_html(matches, players, pm, mg)
    print("✅ Xong!")

if __name__ == "__main__":
    main()
