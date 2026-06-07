#!/usr/bin/env python3
"""
Sync LAIRAI FC stats from Google Sheet → data.js
Usage: python3 scripts/sync_stats.py
Requires: GOOGLE_CREDENTIALS env var (service account JSON)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

SHEET_ID = "1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS = os.path.join(REPO_ROOT, "data.js")

RESULT_MAP = {"Thắng": "W", "Thua": "L", "Hòa": "D"}


# ── helpers ────────────────────────────────────────────────────────────────

def safe_int(val, default=0):
    try:
        return int(str(val).replace(",", "").replace(".", "").strip())
    except Exception:
        return default


def find_header_row(rows, *required):
    """Return index of first row containing all required strings."""
    for i, row in enumerate(rows):
        joined = " ".join(str(c) for c in row)
        if all(kw in joined for kw in required):
            return i
    return -1


def col_idx(header_row, *candidates):
    """Return first column index where any candidate appears."""
    for i, c in enumerate(header_row):
        for cand in candidates:
            if cand in str(c):
                return i
    return -1


# ── Google Sheets connection ───────────────────────────────────────────────

def connect():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Installing gspread and google-auth …")
        os.system(f"{sys.executable} -m pip install gspread google-auth -q")
        import gspread
        from google.oauth2.service_account import Credentials

    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        sys.exit("ERROR: Set GOOGLE_CREDENTIALS environment variable (service account JSON)")

    creds = Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(creds)


def get_worksheet_rows(spreadsheet):
    """Return all rows from the 2026 worksheet (first sheet matching '2026' or sheet 0)."""
    for ws in spreadsheet.worksheets():
        if "2026" in ws.title:
            print(f"  Using worksheet: {ws.title!r}")
            return ws.get_all_values()
    ws = spreadsheet.worksheets()[0]
    print(f"  Fallback worksheet: {ws.title!r}")
    return ws.get_all_values()


# ── parsers ────────────────────────────────────────────────────────────────

def parse_matches(rows):
    """Extract match schedule → list of match dicts, sorted by week."""
    hi = find_header_row(rows, "Đối thủ", "Kết quả")
    if hi == -1:
        print("  WARNING: match schedule section not found")
        return []

    h = rows[hi]
    c_wk  = col_idx(h, "Tuần")
    c_dt  = col_idx(h, "Ngày")
    c_san = col_idx(h, "Tên Sân")
    c_vs  = col_idx(h, "Đối thủ")
    c_gf  = col_idx(h, "Bàn Thắng", "Goals For")
    c_ga  = col_idx(h, "Bàn thua", "Goals Against")
    c_kq  = col_idx(h, "Kết quả")

    matches = []
    for row in rows[hi + 1:]:
        if not row:
            continue
        wk_str = str(row[c_wk]).strip() if c_wk < len(row) else ""
        if "Tuần" not in wk_str:
            continue
        m = re.search(r"\d+", wk_str)
        if not m:
            continue
        wk = int(m.group())

        kq = str(row[c_kq]).strip() if c_kq < len(row) else ""
        if kq not in RESULT_MAP:
            continue  # nghỉ / no result

        dt_raw = str(row[c_dt]).strip() if c_dt < len(row) else ""
        parts = dt_raw.split("/")
        dt = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else dt_raw

        gf = safe_int(row[c_gf]) if c_gf < len(row) else 0
        ga = safe_int(row[c_ga]) if c_ga < len(row) else 0
        venue = str(row[c_san]).strip() if c_san < len(row) else ""

        matches.append({"wk": wk, "dt": dt, "vs": str(row[c_vs]).strip(), "gf": gf, "ga": ga,
                         "r": RESULT_MAP[kq], "v": venue})

    matches.sort(key=lambda m: m["wk"])
    return matches


def parse_players_and_pm(rows, matches):
    """Extract player list and per-match goal matrix."""
    # Find player header: must have Goals, Match, Biệt danh
    hi = find_header_row(rows, "Goals", "Match", "Biệt danh")
    if hi == -1:
        hi = find_header_row(rows, "Goals", "Match", "Vị trí")
    if hi == -1:
        print("  WARNING: player table not found")
        return [], {}

    h = rows[hi]
    c_nick = col_idx(h, "Biệt danh")
    c_pos  = col_idx(h, "Vị trí")
    c_no   = col_idx(h, "Số áo")
    c_g    = col_idx(h, "Goals")
    c_m    = col_idx(h, "Match")
    c_w    = col_idx(h, "Thắng")
    c_d    = col_idx(h, "Hòa")
    c_l    = col_idx(h, "Thua")
    c_gf   = col_idx(h, "GF")
    c_ga   = col_idx(h, "GA")
    c_gd   = col_idx(h, "GD")

    # Collect weekly columns: Tuần N → column index
    week_col = {}
    for i, cell in enumerate(h):
        wm = re.match(r"Tuần\s*(\d+)$", str(cell).strip())
        if wm:
            week_col[int(wm.group(1))] = i

    match_weeks = [m["wk"] for m in matches]
    total = len(matches)

    players = []
    pm = {}

    # Skip the aggregate "team totals" row (row 0 after header, all numbers)
    data_start = hi + 1
    while data_start < len(rows):
        first = str(rows[data_start][0]).strip()
        if first.lstrip("-").isdigit() and int(first) >= 1:
            break
        data_start += 1

    for row in rows[data_start:]:
        if not row or len(row) < 5:
            continue
        try:
            tt = int(str(row[0]).strip())
        except Exception:
            continue  # not a player row

        nick = str(row[c_nick]).strip() if c_nick >= 0 and c_nick < len(row) else ""
        if not nick:
            continue

        goals = safe_int(row[c_g]) if c_g >= 0 and c_g < len(row) else 0
        played = safe_int(row[c_m]) if c_m >= 0 and c_m < len(row) else 0

        # Skip rows where sheet hasn't filled in match count yet
        # (but keep players with 0 goals if they have matches)
        if played == 0 and goals == 0:
            # Check if any weekly column is TRUE/non-zero
            has_data = False
            for wk, ci in week_col.items():
                if ci < len(row):
                    v = str(row[ci]).strip().upper()
                    if v not in ("", "FALSE", "0"):
                        has_data = True
                        break
            if not has_data:
                continue

        pos  = str(row[c_pos]).strip() if c_pos >= 0 and c_pos < len(row) else "MF"
        no   = str(row[c_no]).strip()  if c_no  >= 0 and c_no  < len(row) else ""
        w    = safe_int(row[c_w])  if c_w  >= 0 and c_w  < len(row) else 0
        d    = safe_int(row[c_d])  if c_d  >= 0 and c_d  < len(row) else 0
        l    = safe_int(row[c_l])  if c_l  >= 0 and c_l  < len(row) else 0
        gf   = safe_int(row[c_gf]) if c_gf >= 0 and c_gf < len(row) else 0
        ga   = safe_int(row[c_ga]) if c_ga >= 0 and c_ga < len(row) else 0
        gd   = safe_int(row[c_gd]) if c_gd >= 0 and c_gd < len(row) else gf - ga

        mp = round(played / total, 2) if total > 0 else 0
        wp = round(w / played, 4) if played > 0 else 0

        # Build PM array for this player (one entry per match, in match order)
        player_pm = []
        for match_wk in match_weeks:
            ci = week_col.get(match_wk, -1)
            if ci < 0 or ci >= len(row):
                player_pm.append(None)
                continue
            v = str(row[ci]).strip().upper()
            if v in ("", "FALSE"):
                player_pm.append(None)
            elif v == "TRUE":
                player_pm.append(0)
            else:
                try:
                    player_pm.append(max(int(v), 0))
                except Exception:
                    player_pm.append(None)

        # Recompute played count from PM (more reliable than sheet's Match column)
        pm_played = sum(1 for v in player_pm if v is not None)
        if played == 0 and pm_played > 0:
            played = pm_played
            mp = round(played / total, 2)

        # Compute form: last 5 matches → W/D/L if played, N if not
        last5 = matches[-5:]
        fa = []
        for match in last5:
            idx = match_weeks.index(match["wk"])
            val = player_pm[idx] if idx < len(player_pm) else None
            fa.append(match["r"] if val is not None else "N")

        t = "main" if played >= 3 else "sub"

        players.append({
            "n": nick, "p": pos, "no": no, "g": goals, "m": played,
            "mp": mp, "wp": wp, "fa": fa,
            "w": w, "d": d, "l": l, "gf": gf, "ga": ga, "gd": gd, "t": t,
        })
        pm[nick] = player_pm

    return players, pm


def parse_goals(rows):
    """Extract goal tracker → MG dict keyed by week number."""
    hi = find_header_row(rows, "Hiệp", "Assist", "Loại bàn thắng")
    if hi == -1:
        print("  WARNING: goal tracker section not found")
        return {}

    MG = {}
    current_wk = None

    for row in rows[hi + 1:]:
        if not row or all(str(c).strip() == "" for c in row[:3]):
            continue

        wk_str = str(row[0]).strip()
        if "Tuần" in wk_str:
            m = re.search(r"\d+", wk_str)
            if m:
                current_wk = int(m.group())

        if current_wk is None:
            continue

        hiep     = str(row[1]).strip() if len(row) > 1 else ""
        scorer   = str(row[2]).strip() if len(row) > 2 else ""
        assist   = str(row[3]).strip() if len(row) > 3 else ""
        gtype    = str(row[4]).strip() if len(row) > 4 else "Thường"

        if not scorer and not gtype:
            continue

        if current_wk not in MG:
            MG[current_wk] = {"s": [], "ms": [], "c": [], "pf": 0, "ps": 0}

        h = 1 if "1" in hiep else 2

        gtype_lower = gtype.lower()

        if "hỏng" in gtype_lower or "hong" in gtype_lower:
            if scorer:
                MG[current_wk]["ms"].append({"sc": scorer, "h": h})

        elif "bàn thua" in gtype_lower or "ban thua" in gtype_lower:
            # Conceded goal — scorer field holds GK name
            if scorer:
                MG[current_wk]["c"].append({"gk": scorer, "h": h})

        elif scorer:
            t = "pen" if "pen" in gtype_lower else "normal"
            entry = {"sc": scorer, "t": t, "h": h}
            if assist:
                entry["as"] = assist
            MG[current_wk]["s"].append(entry)

    return MG


def parse_gk_sheet(rows):
    """Extract GK aggregate stats → {name: {h1, h2, pf, ps}}."""
    hi = find_header_row(rows, "Bàn thua H1", "Cản Pen")
    if hi == -1:
        return {}

    gk = {}
    for row in rows[hi + 1:]:
        if not row or not str(row[0]).strip():
            continue
        name = str(row[0]).strip()
        if not name or name.startswith("|") or "Tuần" in name:
            continue

        h1 = safe_int(row[1]) if len(row) > 1 else 0
        h2 = safe_int(row[2]) if len(row) > 2 else 0
        pf = safe_int(row[4]) if len(row) > 4 else 0
        ps = safe_int(row[5]) if len(row) > 5 else 0

        if name not in gk:
            gk[name] = {"h1": 0, "h2": 0, "pf": 0, "ps": 0}
        gk[name]["h1"] += h1
        gk[name]["h2"] += h2
        gk[name]["pf"] += pf
        gk[name]["ps"] += ps

    return gk


# ── JavaScript generation ─────────────────────────────────────────────────

def js_str(s):
    return json.dumps(s, ensure_ascii=False)


def js_match(m):
    return (f'{{wk:{m["wk"]},dt:{js_str(m["dt"])},vs:{js_str(m["vs"])},'
            f'gf:{m["gf"]},ga:{m["ga"]},r:{js_str(m["r"])},v:{js_str(m["v"])}}}')


def js_player(p):
    fa = json.dumps(p["fa"], ensure_ascii=False)
    return (f'{{n:{js_str(p["n"])},p:{js_str(p["p"])},no:{js_str(p["no"])},'
            f'g:{p["g"]},m:{p["m"]},mp:{p["mp"]},wp:{p["wp"]},fa:{fa},'
            f'w:{p["w"]},d:{p["d"]},l:{p["l"]},gf:{p["gf"]},ga:{p["ga"]},gd:{p["gd"]},t:{js_str(p["t"])}}}')


def js_pm_row(vals):
    return "[" + ",".join("null" if v is None else str(v) for v in vals) + "]"


def js_mg(MG):
    if not MG:
        return "const MG={};"
    lines = ["const MG={"]
    entries = []
    for wk in sorted(MG):
        mg = MG[wk]
        parts = []

        if mg.get("s"):
            goals = []
            for g in mg["s"]:
                e = f'{{sc:{js_str(g["sc"])},t:{js_str(g["t"])},h:{g["h"]}'
                if "as" in g:
                    e += f',as:{js_str(g["as"])}'
                e += "}"
                goals.append(e)
            parts.append(f's:[{",".join(goals)}]')

        if mg.get("ms"):
            ms = [f'{{sc:{js_str(g["sc"])},h:{g["h"]}}}' for g in mg["ms"]]
            parts.append(f'ms:[{",".join(ms)}]')

        if mg.get("c"):
            c = [f'{{gk:{js_str(c["gk"])},h:{c["h"]}}}' for c in mg["c"]]
            parts.append(f'c:[{",".join(c)}]')

        parts.append(f'pf:{mg.get("pf",0)},ps:{mg.get("ps",0)}')
        entries.append(f'  {wk}:{{{",".join(parts)}}}')

    lines.append(",\n".join(entries))
    lines.append("};")
    return "\n".join(lines)


AGGREGATE_CODE = """\
// Compute aggregates from goal detail
const AST_H={},PEN={},HGF={h1:0,h2:0},HGA={h1:0,h2:0},GKD={};
Object.values(MG).forEach(mg=>{
  (mg.s||[]).forEach(g=>{
    if(g.as){if(!AST_H[g.as])AST_H[g.as]={h1:0,h2:0};g.h===1?AST_H[g.as].h1++:AST_H[g.as].h2++;}
    if(g.t==="pen"){if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].sc++}
    g.h===1?HGF.h1++:HGF.h2++;
  });
  (mg.ms||[]).forEach(g=>{if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].ms++});
  (mg.c||[]).forEach(c=>{
    if(!GKD[c.gk])GKD[c.gk]={conc:0,h1:0,h2:0,pf:0,ps:0};
    GKD[c.gk].conc++;c.h===1?(GKD[c.gk].h1++,HGA.h1++):(GKD[c.gk].h2++,HGA.h2++);
  });
  if(mg.pf)Object.values(GKD).forEach(d=>{d.pf+=mg.pf;d.ps+=mg.ps||0});
});
// Supplement GKD with sheet aggregate for any GK not yet in per-match detail
Object.entries(GKD_SHEET).forEach(([k,v])=>{
  if(!GKD[k]){GKD[k]={conc:v.h1+v.h2,h1:v.h1,h2:v.h2,pf:v.pf,ps:v.ps};HGA.h1+=v.h1;HGA.h2+=v.h2;}
});
const AST=Object.fromEntries(Object.entries(AST_H).map(([k,v])=>[k,v.h1+v.h2]));"""


def build_data_js(matches, players, pm, MG, gk_sheet):
    if not matches:
        return None

    w = sum(1 for m in matches if m["r"] == "W")
    d = sum(1 for m in matches if m["r"] == "D")
    l = sum(1 for m in matches if m["r"] == "L")
    gf = sum(m["gf"] for m in matches)
    ga = sum(m["ga"] for m in matches)
    form = [m["r"] for m in matches[-5:]]
    latest_wk = max(m["wk"] for m in matches)
    mg_wks = sorted(MG.keys())
    detail_wk = max(mg_wks) if mg_wks else 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"// AUTO-GENERATED — do not edit by hand.",
        f"// Run: python3 scripts/sync_stats.py  OR  trigger GitHub Action 'Sync Stats from Sheet'",
        f"// Last synced: {now}",
        "",
        f"const T={{m:{len(matches)},gf:{gf},ga:{ga},gd:{gf-ga},w:{w},d:{d},l:{l},"
        f"form:{json.dumps(form, ensure_ascii=False)}}};",
        "T.pts=T.w*3+T.d; T.ppg=T.pts/T.m;",
        "",
        "const M=[",
        *[f"  {js_match(m)}{',' if i < len(matches)-1 else ''}" for i, m in enumerate(matches)],
        "];",
        "",
        "// s=scored  ms=missed pen  c=conceded [{gk,h}]  pf/ps=pen faced/saved",
        js_mg(MG),
        "",
        "// GK aggregate from sheet (fallback when per-match detail is missing)",
        "const GKD_SHEET=" + json.dumps(gk_sheet, ensure_ascii=False) + ";",
        "",
        AGGREGATE_CODE,
        "",
        "const P=[",
        *[f"  {js_player(p)}{',' if i < len(players)-1 else ''}" for i, p in enumerate(players)],
        "];",
        "",
        "const PM={",
        *[f"  {js_str(p['n'])}:{js_pm_row(pm[p['n']])}{',' if i < len(players)-1 else ''}"
          for i, p in enumerate(players) if p["n"] in pm],
        "};",
    ]

    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────

def main():
    print("Connecting to Google Sheets …")
    gc = connect()
    sh = gc.open_by_key(SHEET_ID)

    print("Reading worksheet …")
    rows = get_worksheet_rows(sh)
    print(f"  {len(rows)} rows loaded")

    print("Parsing match schedule …")
    matches = parse_matches(rows)
    print(f"  {len(matches)} matches found: weeks {[m['wk'] for m in matches]}")

    print("Parsing player stats …")
    players, pm = parse_players_and_pm(rows, matches)
    print(f"  {len(players)} players: {[p['n'] for p in players]}")

    print("Parsing goal detail …")
    MG = parse_goals(rows)
    print(f"  Goal detail for weeks: {sorted(MG.keys())}")

    print("Parsing GK aggregate …")
    gk_sheet = parse_gk_sheet(rows)
    print(f"  GK sheet data: {gk_sheet}")

    print("Building data.js …")
    content = build_data_js(matches, players, pm, MG, gk_sheet)
    if content is None:
        sys.exit("ERROR: No match data found — sheet may be empty or structure unrecognised")

    # Read existing file
    try:
        with open(DATA_JS, encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""

    # Strip comment header for comparison (timestamps change every run)
    def strip_header(s):
        return "\n".join(ln for ln in s.splitlines() if not ln.startswith("// "))

    if strip_header(content) == strip_header(existing):
        print("No data changes detected — data.js unchanged.")
        return

    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write(content)

    latest_wk = max(m["wk"] for m in matches)
    mg_wks = sorted(MG.keys())
    detail_wk = max(mg_wks) if mg_wks else 0
    print(f"✓ data.js updated — {len(matches)} matches, {len(players)} players, latest Tuần {latest_wk}")
    if detail_wk:
        print(f"  Goal detail through Tuần {detail_wk}")


if __name__ == "__main__":
    main()
