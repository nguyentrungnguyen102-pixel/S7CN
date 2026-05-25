#!/usr/bin/env python3
"""
Update stats.html from Google Sheets (gid=602325894).
The sheet must be shared: Anyone with the link → Viewer.
Run: python scripts/update_stats.py
"""
import re, json, sys
import requests

SHEET_ID = "1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68"
STATS_GID = "602325894"
STATS_HTML = "stats.html"

# --- helpers ---
def fetch_gviz(gid):
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
           f"/gviz/tq?tqx=out:json&gid={gid}&hl=vi")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    m = re.search(r'setResponse\(([\s\S]*)\);\s*$', r.text)
    if not m:
        raise ValueError(f"Cannot parse gviz response (first 300 chars):\n{r.text[:300]}")
    data = json.loads(m.group(1))
    result = []
    for row in (data["table"].get("rows") or []):
        if not row:
            result.append([])
            continue
        cells = []
        for cell in (row.get("c") or []):
            cells.append(cell.get("v") if cell else None)
        result.append(cells)
    return result

def sv(v, d=""):
    return str(v).strip() if v is not None else d

def iv(v, d=0):
    if v is None:
        return d
    try:
        return int(round(float(str(v).replace(",", "."))))
    except Exception:
        return d

def fv(v, d=0.0):
    if v is None:
        return d
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return d

def pv(v):
    """Percentage → float 0-1"""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        x = float(v)
        return x / 100.0 if x > 1 else x
    s = str(v).replace("%", "").replace(",", ".").strip()
    try:
        x = float(s)
        return x / 100.0 if x > 1 else x
    except Exception:
        return 0.0

def row_sv(row):
    return [sv(v) for v in row]

def jstr(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

# --- fetch ---
print(f"Fetching sheet gid={STATS_GID}...")
rows = fetch_gviz(STATS_GID)
print(f"Got {len(rows)} rows")

# ============================================================
# FIND MATCH SCHEDULE SECTION
# Header: first cell "Tuần", has "Đối thủ" or "Tên Sân" somewhere
# ============================================================
match_hdr_idx = None
match_col = {}

for i, row in enumerate(rows):
    if not row or len(row) < 5:
        continue
    rs = row_sv(row)
    first = rs[0]
    if first == "Tuần" and any("Đối thủ" in x or "Bàn Thắng" in x or "Tên Sân" in x
                               for x in rs[:12]):
        match_hdr_idx = i
        for j, v in enumerate(row):
            key = sv(v)
            if key:
                match_col[key] = j
        print(f"Match schedule header at row {i}: {rs[:8]}")
        break

# ============================================================
# PARSE MATCHES
# ============================================================
matches = []

if match_hdr_idx is not None:
    wk_c  = match_col.get("Tuần", 0)
    dt_c  = match_col.get("Ngày", 1)
    ven_c = match_col.get("Tên Sân", 4)
    vs_c  = match_col.get("Đối thủ", 5)
    att_c = match_col.get("Điểm danh", 6)
    gf_c  = match_col.get("Bàn Thắng", 7)
    # "Bàn thua" may also be "Bàn Thua"
    ga_c  = match_col.get("Bàn thua", match_col.get("Bàn Thua", 9))
    res_c = match_col.get("Kết quả", 10)

    for row in rows[match_hdr_idx + 1:]:
        if not row:
            continue
        wk_raw = row[wk_c] if wk_c < len(row) else None
        wk_num = iv(wk_raw)
        if wk_num <= 0:
            if wk_raw is not None and sv(wk_raw) not in ("", "Tuần"):
                continue   # skip section-end sentinel rows
            if wk_raw is None and all(
                    (row[j] is None if j < len(row) else True) for j in range(5)):
                continue  # blank row, keep scanning
            continue

        res_raw = sv(row[res_c] if res_c < len(row) else None).upper()
        # Normalize W/D/L from Vietnamese or English
        RES_MAP = {
            "W": "W", "D": "D", "L": "L",
            "THẮNG": "W", "HÒA": "D", "THUA": "L",
            "T": "W", "H": "D", "B": "L",
        }
        res = RES_MAP.get(res_raw)
        if not res:
            continue   # not a played match

        dt_raw = sv(row[dt_c] if dt_c < len(row) else None)
        gf_val = iv(row[gf_c] if gf_c < len(row) else None)
        ga_val = iv(row[ga_c] if ga_c < len(row) else None)
        venue  = sv(row[ven_c] if ven_c < len(row) else None)
        opp    = sv(row[vs_c] if vs_c < len(row) else None)
        att    = iv(row[att_c] if att_c < len(row) else None)

        # Date format normalisation: keep DD/MM
        # gviz sometimes returns dates as Date(year,mon,day) objects
        if dt_raw.startswith("Date("):
            m2 = re.match(r"Date\((\d+),(\d+),(\d+)\)", dt_raw)
            if m2:
                day = int(m2.group(3))
                mon = int(m2.group(2)) + 1  # JS months are 0-based
                dt_raw = f"{day:02d}/{mon:02d}"

        matches.append({"wk": wk_num, "dt": dt_raw, "vs": opp,
                        "gf": gf_val, "ga": ga_val, "r": res,
                        "v": venue, "a": att})

    matches.sort(key=lambda x: x["wk"])
    print(f"Parsed {len(matches)} matches")
else:
    print("WARNING: match schedule section not found — keeping existing M data")

# ============================================================
# FIND PLAYER STATS SECTION
# Header row: TT in col 0, "Goals" and "Match" present
# ============================================================
player_hdr_idx = None
player_col = {}
week_cols = {}   # week_number → col_index

for i, row in enumerate(rows):
    if not row or len(row) < 10:
        continue
    rs = row_sv(row)
    if rs[0] == "TT" and "Goals" in rs and "Match" in rs:
        player_hdr_idx = i
        for j, v in enumerate(row):
            key = sv(v).strip()
            if not key:
                continue
            player_col[key] = j
            wm = re.match(r"Tuần\s*(\d+)$", key)
            if wm:
                week_cols[int(wm.group(1))] = j
        print(f"Player header at row {i}, week cols: {sorted(week_cols.keys())[:5]}…")
        break

# ============================================================
# PARSE PLAYERS
# ============================================================
players = []
pm_data = {}   # nickname → [goals_or_None per played match]

# Sub-player names (can be extended as needed)
SUB_NAMES = {"Anh Sơn", "Chí Quỹ", "Tiến", "An", "Tuấn", "Mới"}

played_weeks = sorted(m["wk"] for m in matches)
match_result_by_wk = {m["wk"]: m["r"] for m in matches}

if player_hdr_idx is not None:
    hrow = rows[player_hdr_idx]

    # Locate columns by name (robust to column order shifts)
    def col(name, fallback=-1):
        # try exact, then strip, then partial
        if name in player_col:
            return player_col[name]
        for k, v in player_col.items():
            if k.strip() == name.strip():
                return v
        return fallback

    tt_c    = col("TT", 0)
    name_c  = col("Họ và tên", 1)
    nick_c  = col("Biệt danh", 2)
    pos_c   = col("Vị trí", 6)
    num_c   = col("Số áo", 8)
    goals_c = col("Goals", 10)
    match_c = col("Match", 11)
    wpct_c  = col("% Win", 13)
    pi_c    = col("Point Impact", 16)
    win_c   = col("Thắng", 17)
    draw_c  = col("Hòa", 18)
    lose_c  = col("Thua", 19)
    gf_c    = col("GF", 20)
    ga_c2   = col("GA", 21)
    gd_c    = col("GD", 22)

    # Fallback: scan header row for known labels
    for j, v in enumerate(hrow):
        k = sv(v).strip()
        if k == "TT":            tt_c    = j
        elif k in ("Họ và tên", "Họ và tên "):   name_c  = j
        elif k == "Biệt danh":  nick_c  = j
        elif k == "Vị trí":     pos_c   = j
        elif k == "Số áo":      num_c   = j
        elif k == "Goals":       goals_c = j
        elif k == "Match":       match_c = j
        elif "Win" in k and "%" in k: wpct_c  = j
        elif "Impact" in k:      pi_c    = j
        elif k == "Thắng":       win_c   = j
        elif k == "Hòa":         draw_c  = j
        elif k == "Thua":        lose_c  = j
        elif k == "GF":          gf_c    = j
        elif k == "GA":          ga_c2   = j
        elif k == "GD":          gd_c    = j

    POS_MAP = {
        "FW": "FW", "Tiền đạo": "FW", "Tiền Đạo": "FW",
        "Tiền Đạo, Tiền Vệ Công": "FW",
        "MF": "MF", "Tiền vệ": "MF", "Tiền Vệ": "MF",
        "Tiền Vệ Cánh": "MF", "Tiền vệ trung tâm": "MF",
        "Tiền Vệ , Tiền Đạo": "MF", "Tiền vệ , Tiền Đạo": "MF",
        "DF": "DF", "Hậu vệ": "DF", "Hậu Vệ": "DF",
        "Hậu vệ - Tiền vệ cánh": "DF",
        "GK": "GK", "Thủ môn": "GK", "Thủ Môn": "GK",
        "Thủ môn+ và một vài vị trí khác": "GK",
    }

    # Skip 1 row after header (the weekly count row)
    start_row = player_hdr_idx + 2

    for row in rows[start_row:]:
        if not row:
            continue

        def get(c):
            return row[c] if 0 <= c < len(row) else None

        tt_val = sv(get(tt_c))

        # Determine player type
        is_sub = tt_val.lower().startswith("sub") or tt_val == ""
        is_num = bool(re.match(r"^\d+$", tt_val))
        if not is_num and not is_sub:
            continue

        nick = sv(get(nick_c))
        name = sv(get(name_c))
        display = nick if nick else name
        if not display:
            continue

        match_count = iv(get(match_c))
        if match_count <= 0:
            continue

        goals   = iv(get(goals_c))
        wp      = pv(get(wpct_c))
        pi_val  = fv(get(pi_c))
        wins    = iv(get(win_c))
        draws   = iv(get(draw_c))
        losses  = iv(get(lose_c))
        gf_p    = iv(get(gf_c))
        ga_p    = iv(get(ga_c2))
        gd_p    = iv(get(gd_c))
        num     = sv(get(num_c))
        raw_pos = sv(get(pos_c))

        pos = POS_MAP.get(raw_pos, raw_pos[:2].upper() if raw_pos else "MF")

        total_m = len(matches)
        mp = round(match_count / total_m, 4) if total_m else 0

        # Compute wp from wins/match_count if sheet value missing
        if wp == 0.0 and wins > 0:
            wp = round(wins / match_count, 4)

        # Compute pi from W/D/match if sheet value missing
        if pi_val == 0.0 and match_count > 0:
            pi_val = round((wins * 3 + draws) / match_count, 2)

        # Weekly goals: None=absent, 0=played no goals, N=goals
        weekly = {}
        for wk_num, col_idx in week_cols.items():
            if col_idx < len(row):
                cell = row[col_idx]
                if cell is None or cell is False:
                    weekly[wk_num] = None
                else:
                    weekly[wk_num] = iv(cell, 0)
            else:
                weekly[wk_num] = None

        # PM array indexed by played match order
        pm_arr = [weekly.get(wk) for wk in played_weeks]

        # Compute form (last 5 of ALL played weeks, this player)
        form = []
        for wk in reversed(played_weeks):
            g = weekly.get(wk)
            form.append(match_result_by_wk[wk] if g is not None else "N")
            if len(form) >= 5:
                break
        form.reverse()
        while len(form) < 5:
            form.insert(0, "N")

        ptype = "sub" if (is_sub or display in SUB_NAMES) else "main"

        players.append({
            "n": display, "p": pos, "no": num, "g": goals,
            "m": match_count, "mp": mp, "wp": round(wp, 4),
            "fa": form, "pi": round(pi_val, 2),
            "w": wins, "d": draws, "l": losses,
            "gf": gf_p, "ga": ga_p, "gd": gd_p, "t": ptype,
        })
        pm_data[display] = pm_arr

    print(f"Parsed {len(players)} players")

# ============================================================
# COMPUTE TEAM TOTALS
# ============================================================
if matches:
    T_data = {
        "m": len(matches),
        "gf": sum(m["gf"] for m in matches),
        "ga": sum(m["ga"] for m in matches),
        "gd": sum(m["gf"] - m["ga"] for m in matches),
        "w": sum(1 for m in matches if m["r"] == "W"),
        "d": sum(1 for m in matches if m["r"] == "D"),
        "l": sum(1 for m in matches if m["r"] == "L"),
        "form": [m["r"] for m in matches[-5:]],
    }
else:
    T_data = None

# ============================================================
# GENERATE JAVASCRIPT BLOCKS
# ============================================================
def gen_T(t):
    form = "[" + ",".join(f'"{x}"' for x in t["form"]) + "]"
    return (f'const T={{m:{t["m"]},gf:{t["gf"]},ga:{t["ga"]},gd:{t["gd"]},'
            f'w:{t["w"]},d:{t["d"]},l:{t["l"]},form:{form}}};')

def gen_M(ms):
    lines = [
        f'  {{wk:{m["wk"]},dt:{jstr(m["dt"])},vs:{jstr(m["vs"])},'
        f'gf:{m["gf"]},ga:{m["ga"]},r:{jstr(m["r"])},v:{jstr(m["v"])},a:{m["a"]}}}'
        for m in ms
    ]
    return "const M=[\n" + ",\n".join(lines) + "\n];"

def gen_P(ps):
    lines = []
    for p in ps:
        fa = "[" + ",".join(f'"{x}"' for x in p["fa"]) + "]"
        lines.append(
            f'  {{n:{jstr(p["n"])},p:{jstr(p["p"])},no:{jstr(p["no"])},'
            f'g:{p["g"]},m:{p["m"]},mp:{p["mp"]},wp:{p["wp"]},'
            f'fa:{fa},pi:{p["pi"]},w:{p["w"]},d:{p["d"]},l:{p["l"]},'
            f'gf:{p["gf"]},ga:{p["ga"]},gd:{p["gd"]},t:{jstr(p["t"])}}}'
        )
    return "const P=[\n" + ",\n".join(lines) + "\n];"

def gen_PM(pm):
    lines = []
    for name, arr in pm.items():
        vals = ",".join("null" if v is None else str(v) for v in arr)
        lines.append(f'  {jstr(name)}:[{vals}]')
    return "const PM={\n" + ",\n".join(lines) + "\n};"

# ============================================================
# UPDATE stats.html
# ============================================================
if not (T_data and matches and players):
    print("WARNING: Not enough data parsed — aborting update.")
    if not T_data:   print("  missing T_data")
    if not matches:  print("  missing matches")
    if not players:  print("  missing players")
    sys.exit(1)

with open(STATS_HTML, "r", encoding="utf-8") as fh:
    html = fh.read()

new_block = "\n".join([
    "// DATA_START — auto-generated by scripts/update_stats.py, do not edit manually",
    gen_T(T_data),
    "T.ppg=(T.w*3+T.d)/T.m;",
    "",
    gen_M(matches),
    "",
    gen_P(players),
    "",
    gen_PM(pm_data),
    "// DATA_END — end of auto-generated data",
])

# Replace everything between DATA_START and DATA_END (inclusive)
pattern = r"// DATA_START[^\n]*\n[\s\S]*?// DATA_END[^\n]*"
new_html, n_subs = re.subn(pattern, new_block, html)

if n_subs == 0:
    print("ERROR: DATA_START/DATA_END markers not found in stats.html")
    sys.exit(1)

# Update subtitle "Cập nhật sau X trận"
total_m = T_data["m"]
new_html = re.sub(
    r"Cập nhật sau \d+ trận",
    f"Cập nhật sau {total_m} trận",
    new_html,
)

with open(STATS_HTML, "w", encoding="utf-8") as fh:
    fh.write(new_html)

print(f"✓ stats.html updated: {total_m} matches, {len(players)} players")
