#!/usr/bin/env python3
"""
Auto-update stats.html from Google Sheets data.
Reads match schedule, player stats, and goal details,
then regenerates the JavaScript data section in stats.html.

Usage:
  GOOGLE_CREDENTIALS='<service-account-json>' python scripts/update_stats.py

Setup:
  pip install gspread google-auth
"""

import json
import os
import re
import sys
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68"
SHEET_GID = 602325894
STATS_HTML = os.path.join(os.path.dirname(__file__), "..", "stats.html")

# Position normalization
POS_NORMALIZE = {
    "RM": "CM",
    "Tiền vệ": "CM",
    "Hậu vệ": "DF",
    "Tiền đạo": "FW",
    "Thủ môn": "GK",
}


def connect():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS env var not set. "
                         "Set it to the service account JSON content.")
    creds_data = json.loads(creds_json)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)
    # Try to get the specific sheet tab by gid
    try:
        ws = sh.get_worksheet_by_id(SHEET_GID)
        if ws:
            return ws
    except Exception:
        pass
    return sh.get_worksheet(0)


def find_table(rows, keywords):
    """Return (header_row_index, header_row) for a table whose header contains all keywords."""
    for i, row in enumerate(rows):
        text = " | ".join(str(c) for c in row).lower()
        if all(kw.lower() in text for kw in keywords):
            return i, row
    return -1, None


def col_index(header, keywords):
    """Find column index by matching any keyword."""
    for i, v in enumerate(header):
        if any(kw.lower() in str(v).lower() for kw in keywords):
            return i
    return -1


def safe_int(v):
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return 0


def parse_match_schedule(rows):
    """Parse 2026 match schedule → list of match dicts."""
    hi, header = find_table(rows, ["Tuần", "Đối thủ", "Kết quả"])
    if hi == -1:
        sys.exit("ERROR: Cannot find match schedule table in sheet.")

    c_wk   = col_index(header, ["Tuần"])
    c_date = col_index(header, ["Ngày"])
    c_ven  = col_index(header, ["Tên Sân"])
    c_opp  = col_index(header, ["Đối thủ"])
    c_gf   = col_index(header, ["Bàn Thắng", "Goals For"])
    c_ga   = col_index(header, ["Bàn thua", "Goals Against"])
    c_res  = col_index(header, ["Kết quả"])

    needed = [c_wk, c_date, c_ven, c_opp, c_gf, c_ga, c_res]
    if -1 in needed:
        sys.exit(f"ERROR: Missing match schedule columns. Found: {needed}")

    matches = []
    for row in rows[hi + 1:]:
        if not row:
            break
        wk_s = str(row[c_wk]).strip() if c_wk < len(row) else ""
        if not wk_s.lower().startswith("tuần"):
            break
        res_s = str(row[c_res]).strip() if c_res < len(row) else ""
        if res_s not in ("Thắng", "Hòa", "Thua"):
            continue  # rest week or future match

        m = re.search(r"\d+", wk_s)
        if not m:
            continue
        wk = int(m.group())

        date_s = str(row[c_date]).strip() if c_date < len(row) else ""
        parts = date_s.split("/")
        date_fmt = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else date_s

        gf = safe_int(row[c_gf] if c_gf < len(row) else 0)
        ga = safe_int(row[c_ga] if c_ga < len(row) else 0)
        venue = str(row[c_ven]).strip() if c_ven < len(row) else ""
        opp = str(row[c_opp]).strip() if c_opp < len(row) else ""
        r = "W" if res_s == "Thắng" else "D" if res_s == "Hòa" else "L"

        matches.append({
            "wk": wk, "dt": date_fmt, "vs": opp,
            "gf": gf, "ga": ga, "r": r, "v": venue,
        })

    return matches


def parse_players(rows, match_weeks):
    """Parse player roster → (players_list, pm_dict)."""
    hi, header = find_table(rows, ["Biệt danh", "Goals", "Match"])
    if hi == -1:
        sys.exit("ERROR: Cannot find player roster table in sheet.")

    c_tt    = col_index(header, ["TT"])
    c_alias = col_index(header, ["Biệt danh"])
    c_pos   = col_index(header, ["Vị trí"])
    c_no    = col_index(header, ["Số áo"])
    c_goals = col_index(header, ["Goals"])
    c_match = col_index(header, ["Match"])
    c_w     = col_index(header, ["Thắng"])
    c_d     = col_index(header, ["Hòa"])
    c_l     = col_index(header, ["Thua"])
    c_gf    = col_index(header, ["GF"])
    c_ga    = col_index(header, ["GA"])

    # Build week → column index map (header has Tuần 52 … Tuần 1)
    week_col_map = {}
    for i, v in enumerate(header):
        mm = re.match(r"Tuần\s*(\d+)", str(v).strip())
        if mm:
            week_col_map[int(mm.group(1))] = i

    players = []
    pm = {}
    total = len(match_weeks)

    for row in rows[hi + 1:]:
        if not row or len(row) < 11:
            continue
        alias = str(row[c_alias]).strip() if c_alias != -1 and c_alias < len(row) else ""
        if not alias or ":-:" in alias:
            continue
        try:
            goals = safe_int(row[c_goals] if c_goals != -1 and c_goals < len(row) else 0)
            match_cnt = safe_int(row[c_match] if c_match != -1 and c_match < len(row) else 0)
        except Exception:
            continue

        # Skip rows with empty alias or obviously invalid data
        if not alias:
            continue

        pos = str(row[c_pos]).strip() if c_pos != -1 and c_pos < len(row) else ""
        pos = POS_NORMALIZE.get(pos, pos)
        no  = str(row[c_no]).strip() if c_no != -1 and c_no < len(row) else ""

        w  = safe_int(row[c_w]  if c_w  != -1 and c_w  < len(row) else 0)
        d  = safe_int(row[c_d]  if c_d  != -1 and c_d  < len(row) else 0)
        l  = safe_int(row[c_l]  if c_l  != -1 and c_l  < len(row) else 0)
        gf = safe_int(row[c_gf] if c_gf != -1 and c_gf < len(row) else 0)
        ga = safe_int(row[c_ga] if c_ga != -1 and c_ga < len(row) else 0)
        gd = gf - ga

        mp = round(match_cnt / total, 2) if total > 0 else 0
        wp = round(w / match_cnt, 3) if match_cnt > 0 else 0

        tt_val = str(row[c_tt]).strip() if c_tt != -1 and c_tt < len(row) else ""
        p_type = "sub" if str(tt_val).lower() == "sub" else "main"

        # Per-match presence/goals array
        pm_vals = []
        for wk in match_weeks:
            if wk in week_col_map:
                ci = week_col_map[wk]
                val = str(row[ci]).strip() if ci < len(row) else ""
                if val.upper() == "FALSE" or val == "":
                    pm_vals.append(None)
                elif val.upper() == "TRUE":
                    pm_vals.append(0)
                else:
                    try:
                        pm_vals.append(int(val))
                    except ValueError:
                        pm_vals.append(0)
            else:
                pm_vals.append(None)

        players.append({
            "n": alias, "p": pos, "no": no,
            "g": goals, "m": match_cnt, "mp": mp, "wp": wp,
            "fa": [],  # filled after
            "w": w, "d": d, "l": l,
            "gf": gf, "ga": ga, "gd": gd,
            "t": p_type,
        })
        pm[alias] = pm_vals

    return players, pm


def compute_form(pm_vals, matches):
    """Last 5 match form: W/D/L if played, N if absent."""
    fa = []
    for i in range(len(matches) - 1, -1, -1):
        if len(fa) >= 5:
            break
        played = i < len(pm_vals) and pm_vals[i] is not None
        fa.append(matches[i]["r"] if played else "N")
    return list(reversed(fa))


def parse_goal_log(rows):
    """Parse goal/assist log → MG dict keyed by week number."""
    hi, header = find_table(rows, ["Hiệp", "Assist", "Loại"])
    if hi == -1:
        print("WARNING: Goal log table not found; MG will be empty.")
        return {}

    c_wk     = col_index(header, ["Tuần"])
    c_half   = col_index(header, ["Hiệp"])
    c_scorer = col_index(header, ["Goals", "Scorer", "Ghi bàn"])
    c_assist = col_index(header, ["Assist"])
    c_type   = col_index(header, ["Loại"])

    mg = {}
    cur_week = None

    for row in rows[hi + 1:]:
        if not row:
            break
        # Check for new week
        wk_s = str(row[c_wk]).strip() if c_wk != -1 and c_wk < len(row) else ""
        if wk_s.lower().startswith("tuần"):
            m = re.search(r"\d+", wk_s)
            if m:
                cur_week = int(m.group())
        if cur_week is None:
            continue

        if cur_week not in mg:
            mg[cur_week] = {"s": [], "ms": [], "c": [], "pf": 0, "ps": 0}

        half_s   = str(row[c_half]   if c_half   != -1 and c_half   < len(row) else "").strip()
        scorer_s = str(row[c_scorer] if c_scorer != -1 and c_scorer < len(row) else "").strip()
        assist_s = str(row[c_assist] if c_assist != -1 and c_assist < len(row) else "").strip()
        type_s   = str(row[c_type]   if c_type   != -1 and c_type   < len(row) else "").strip()

        half = 1 if "H1" in half_s.upper() else 2

        if "Hỏng" in type_s or "Pen (H" in type_s:
            if scorer_s:
                mg[cur_week]["ms"].append({"sc": scorer_s, "h": half})
        elif scorer_s:
            t = "pen" if "Pen" in type_s else "normal"
            entry = {"sc": scorer_s, "t": t, "h": half}
            if assist_s:
                entry["as"] = assist_s
            mg[cur_week]["s"].append(entry)

    return mg


def parse_gk_stats(rows, match_weeks, mg):
    """Parse GK stats table and add conceded detail to MG where H1/H2 available."""
    hi, header = find_table(rows, ["Tên thủ môn", "Bàn thua H1"])
    if hi == -1:
        print("WARNING: GK stats table not found.")
        return mg

    c_name  = col_index(header, ["Tên thủ môn"])
    c_h1    = col_index(header, ["H1"])
    c_h2    = col_index(header, ["H2"])
    c_pf    = col_index(header, ["Đối mặt", "Pen gặp"])
    c_ps    = col_index(header, ["Cản"])

    # GK rows are newest-match-first (reverse match order)
    reversed_weeks = list(reversed(match_weeks))
    match_idx = 0

    for row in rows[hi + 1:]:
        if not row:
            break
        name = str(row[c_name]).strip() if c_name != -1 and c_name < len(row) else ""
        if not name or ":-:" in name:
            continue

        h1_s = str(row[c_h1]).strip() if c_h1 != -1 and c_h1 < len(row) else ""
        h2_s = str(row[c_h2]).strip() if c_h2 != -1 and c_h2 < len(row) else ""

        # Only build conceded detail if H1/H2 data is present
        if h1_s or h2_s:
            h1 = safe_int(h1_s)
            h2 = safe_int(h2_s)
            pf = safe_int(row[c_pf]) if c_pf != -1 and c_pf < len(row) else 0
            ps = safe_int(row[c_ps]) if c_ps != -1 and c_ps < len(row) else 0

            if match_idx < len(reversed_weeks):
                wk = reversed_weeks[match_idx]
                if wk not in mg:
                    mg[wk] = {"s": [], "ms": [], "c": [], "pf": 0, "ps": 0}
                c_list = ([{"gk": name, "h": 1}] * h1) + ([{"gk": name, "h": 2}] * h2)
                mg[wk]["c"] = c_list
                mg[wk]["pf"] = pf
                mg[wk]["ps"] = ps

        match_idx += 1

    return mg


def build_team(matches):
    """Compute T object from match list."""
    w = sum(1 for m in matches if m["r"] == "W")
    d = sum(1 for m in matches if m["r"] == "D")
    l = sum(1 for m in matches if m["r"] == "L")
    gf = sum(m["gf"] for m in matches)
    ga = sum(m["ga"] for m in matches)
    form = [m["r"] for m in matches[-5:]] if len(matches) >= 5 else [m["r"] for m in matches]
    return {"m": len(matches), "gf": gf, "ga": ga, "gd": gf - ga,
            "w": w, "d": d, "l": l, "form": form}


def to_js(v):
    """Convert Python value to compact JavaScript literal."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(to_js(x) for x in v) + "]"
    if isinstance(v, dict):
        pairs = [f"{json.dumps(k, ensure_ascii=False)}:{to_js(vv)}" for k, vv in v.items()]
        return "{" + ",".join(pairs) + "}"
    return str(v)


def generate_data_js(T, matches, mg, players, pm):
    """Generate the full JavaScript data block."""
    lines = []

    # ── Team ─────────────────────────────────────────────────────────────────
    form_js = to_js(T["form"])
    lines += [
        "// ===== CORE DATA =====",
        (f"const T={{m:{T['m']},gf:{T['gf']},ga:{T['ga']},gd:{T['gd']},"
         f"w:{T['w']},d:{T['d']},l:{T['l']},form:{form_js}}};"),
        "T.pts=T.w*3+T.d; T.ppg=T.pts/T.m;",
        "",
    ]

    # ── Matches ───────────────────────────────────────────────────────────────
    m_items = []
    for m in matches:
        m_items.append(
            f"  {{wk:{m['wk']},dt:{to_js(m['dt'])},vs:{to_js(m['vs'])},"
            f"gf:{m['gf']},ga:{m['ga']},r:{to_js(m['r'])},v:{to_js(m['v'])}}}"
        )
    lines += ["const M=[", ",\n".join(m_items), "];", ""]

    # ── Goal detail ───────────────────────────────────────────────────────────
    lines += [
        "// ===== GOAL DETAIL =====",
        "// s=scored [{sc,as,t:\"normal\"|\"pen\",h:1|2}]  ms=missed pen  c=conceded [{gk,h}]  pf/ps=pen faced/saved",
    ]
    mg_entries = []
    for wk, data in sorted(mg.items()):
        parts = []
        if data.get("s"):
            s_items = []
            for g in data["s"]:
                gp = [f"sc:{to_js(g['sc'])}"]
                if "as" in g:
                    gp.append(f"as:{to_js(g['as'])}")
                gp += [f"t:{to_js(g['t'])}", f"h:{g['h']}"]
                s_items.append("{" + ",".join(gp) + "}")
            parts.append("s:[" + ",".join(s_items) + "]")
        if data.get("ms"):
            ms_items = [f"{{sc:{to_js(g['sc'])},h:{g['h']}}}" for g in data["ms"]]
            parts.append("ms:[" + ",".join(ms_items) + "]")
        if data.get("c"):
            c_items = [f"{{gk:{to_js(c['gk'])},h:{c['h']}}}" for c in data["c"]]
            parts.append("c:[" + ",".join(c_items) + "]")
        pf = data.get("pf", 0)
        ps = data.get("ps", 0)
        if pf:
            parts.append(f"pf:{pf}")
        if ps:
            parts.append(f"ps:{ps}")
        if parts:
            mg_entries.append(f"  {wk}:{{{','.join(parts)}}}")

    lines += ["const MG={", ",\n".join(mg_entries), "};", ""]

    # ── Aggregate computations (unchanged from original) ──────────────────────
    lines += [
        "// Compute aggregates",
        "const AST_H={},PEN={},HGF={h1:0,h2:0},HGA={h1:0,h2:0},GKD={};",
        "Object.values(MG).forEach(mg=>{",
        "  (mg.s||[]).forEach(g=>{",
        "    if(g.as){if(!AST_H[g.as])AST_H[g.as]={h1:0,h2:0};g.h===1?AST_H[g.as].h1++:AST_H[g.as].h2++;}",
        "    if(g.t===\"pen\"){if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].sc++}",
        "    g.h===1?HGF.h1++:HGF.h2++;",
        "  });",
        "  (mg.ms||[]).forEach(g=>{if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].ms++});",
        "  (mg.c||[]).forEach(c=>{",
        "    if(!GKD[c.gk])GKD[c.gk]={conc:0,h1:0,h2:0,pf:0,ps:0};",
        "    GKD[c.gk].conc++;c.h===1?(GKD[c.gk].h1++,HGA.h1++):(GKD[c.gk].h2++,HGA.h2++);",
        "  });",
        "  if(mg.pf)Object.values(GKD).forEach(d=>{d.pf+=mg.pf;d.ps+=mg.ps||0});",
        "});",
        "const AST=Object.fromEntries(Object.entries(AST_H).map(([k,v])=>[k,v.h1+v.h2]));",
        "",
    ]

    # ── Players ───────────────────────────────────────────────────────────────
    lines.append("// ===== PLAYERS =====")
    p_items = []
    for p in players:
        fa_js = to_js(p["fa"])
        p_items.append(
            f"  {{n:{to_js(p['n'])},p:{to_js(p['p'])},no:{to_js(p['no'])},"
            f"g:{p['g']},m:{p['m']},mp:{p['mp']},wp:{p['wp']},"
            f"fa:{fa_js},w:{p['w']},d:{p['d']},l:{p['l']},"
            f"gf:{p['gf']},ga:{p['ga']},gd:{p['gd']},t:{to_js(p['t'])}}}"
        )
    lines += ["const P=[", ",\n".join(p_items), "];", ""]

    # ── Per-match data ────────────────────────────────────────────────────────
    pm_items = []
    for name, vals in pm.items():
        pm_items.append(f"{to_js(name)}:{to_js(vals)}")
    lines.append("const PM={" + ",".join(pm_items) + "};")

    return "\n".join(lines)


def update_html(js_data, T, matches):
    """Replace DATA_START…DATA_END block and update hero section."""
    with open(STATS_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # ── Replace data block ────────────────────────────────────────────────────
    pattern = r"// DATA_START.*?// DATA_END"
    replacement = f"// DATA_START\n{js_data}\n// DATA_END"
    new_html, n = re.subn(pattern, replacement, html, flags=re.DOTALL)
    if n == 0:
        print("ERROR: DATA_START/DATA_END markers not found in stats.html.")
        return False

    # ── Update hero KPI numbers ────────────────────────────────────────────────
    pts = T["w"] * 3 + T["d"]
    wdl = f"{T['w']}W · {T['d']}D · {T['l']}L"

    # Match count
    new_html = re.sub(
        r'(<div class="kp-n">)\d+(</div><div class="kp-l">Trận</div>)',
        rf'\g<1>{T["m"]}\2',
        new_html,
    )
    # W·D·L
    new_html = re.sub(
        r'(<div class="kp-n sm">)\d+W · \d+D · \d+L(</div>)',
        rf'\g<1>{wdl}\2',
        new_html,
    )
    # Points
    new_html = re.sub(
        r'(<div class="kp-n or">)\d+(</div><div class="kp-l">Điểm</div>)',
        rf'\g<1>{pts}\2',
        new_html,
    )
    # Subtitle: "Cập nhật sau N trận"
    new_html = re.sub(
        r"Cập nhật sau \d+ trận",
        f"Cập nhật sau {T['m']} trận",
        new_html,
    )
    # Find the last week with goal detail for the subtitle note
    if matches:
        last_detail_wk = max((wk for wk in [m["wk"] for m in matches]), default=0)
        new_html = re.sub(
            r"Dữ liệu chi tiết từ tuần \d+",
            f"Dữ liệu chi tiết từ tuần {last_detail_wk}",
            new_html,
        )

    with open(STATS_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    return True


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting stats update…")

    print("  → Connecting to Google Sheets…")
    ws = connect()
    print(f"  → Reading '{ws.title}' worksheet…")
    rows = ws.get_all_values()
    print(f"  → Got {len(rows)} rows.")

    print("  → Parsing match schedule…")
    matches = parse_match_schedule(rows)
    print(f"     {len(matches)} played matches found.")
    if not matches:
        sys.exit("ERROR: No matches parsed.")

    match_weeks = [m["wk"] for m in matches]

    print("  → Parsing players…")
    players, pm = parse_players(rows, match_weeks)
    print(f"     {len(players)} players found.")

    print("  → Parsing goal log…")
    mg = parse_goal_log(rows)

    print("  → Parsing GK stats…")
    mg = parse_gk_stats(rows, match_weeks, mg)

    # ── Compute team totals ──────────────────────────────────────────────────
    T_data = build_team(matches)

    # ── Compute player form from PM ──────────────────────────────────────────
    for p in players:
        p["fa"] = compute_form(pm.get(p["n"], []), matches)

    # Filter out players with 0 matches
    active = [p for p in players if p["m"] > 0]
    active_pm = {p["n"]: pm.get(p["n"], [None] * len(matches)) for p in active}

    print("  → Generating JavaScript data…")
    js_data = generate_data_js(T_data, matches, mg, active, active_pm)

    print("  → Updating stats.html…")
    ok = update_html(js_data, T_data, matches)
    if not ok:
        sys.exit(1)

    w = T_data["w"]; d = T_data["d"]; l = T_data["l"]
    pts = w * 3 + d
    print(f"  ✓ Done! {T_data['m']} matches · {w}W {d}D {l}L · {pts} pts")
    print(f"         GF {T_data['gf']} / GA {T_data['ga']} · {len(active)} players")


if __name__ == "__main__":
    main()
