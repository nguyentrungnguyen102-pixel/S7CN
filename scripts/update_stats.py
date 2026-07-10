#!/usr/bin/env python3
"""
update_stats.py - Tự động cập nhật stats.html từ Google Sheets.
Chạy hàng tuần qua GitHub Actions.

Cấu trúc sheet cần có:
  Sheet "Lịch thi đấu": Tuần | Ngày | ... | Tên Sân | Đối thủ | ... | GF | - | GA | Kết quả | ...
  Sheet "Cầu thủ" (index 0): TT | Họ và tên | Biệt danh | ... | Vị trí | ... | Số áo | ... | Goals | Match | ... | Thắng | Hòa | Thua | GF | GA | GD | Tuần 52 .. Tuần 1
  Sheet "Bàn thắng chi tiết": Tuần | Hiệp | Goals | Assist | Loại bàn thắng
  Sheet "Thủ môn": Tên thủ môn | Bàn thua H1 | Bàn thua H2 | Tổng bàn thua | Đối mặt Pen | Cản Pen
"""

import os, re, json, datetime, sys

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("Thiếu thư viện: pip install gspread google-auth")
    sys.exit(1)

# ───────────── CONFIG ─────────────
SPREADSHEET_ID = os.environ.get(
    "SPREADSHEET_ID",
    "1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68",
)
STATS_HTML = os.path.join(os.path.dirname(__file__), "..", "stats.html")
HOME_VENUE = "Giga Arena"

VENUE_MAP = {
    "Etihad Quận 12": "Etihad Q12",
    "Etihad Q12": "Etihad Q12",
    "Lotus Tân Sơn": "Lotus Tân Sơn",
    "ĐH TDTT": "ĐH TDTT",
    "Dĩ An": "Dĩ An",
    "Giga Arena": "Giga Arena",
}
RESULT_MAP = {"Thắng": "W", "Hòa": "D", "Thua": "L"}
DISPLAY_NAME_MAP = {
    "Dương Chí Hoàng": "D.Chí Hoàng",
}


# ───────────── AUTH ─────────────
def get_client():
    raw = os.environ.get("GOOGLE_CREDENTIALS")
    if not raw:
        raise ValueError("Biến môi trường GOOGLE_CREDENTIALS chưa được đặt.")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)


# ───────────── FIND SHEET ─────────────
def find_ws(sh, *keywords):
    """Tìm worksheet có hàng header chứa tất cả từ khoá."""
    for ws in sh.worksheets():
        try:
            row = ws.row_values(1)
            joined = " ".join(str(h) for h in row)
            if all(kw in joined for kw in keywords):
                return ws
        except Exception:
            continue
    return None


def col_of(header, *names):
    """Trả về chỉ số cột đầu tiên khớp tên (0-based), hoặc -1."""
    for name in names:
        try:
            return header.index(name)
        except ValueError:
            continue
    return -1


# ───────────── PARSE MATCHES ─────────────
def parse_matches(ws):
    rows = ws.get_all_values()
    # Tìm hàng header
    hdr, hdr_i = None, 0
    for i, row in enumerate(rows):
        j = " ".join(row)
        if "Đối thủ" in j and "Kết quả" in j:
            hdr, hdr_i = row, i
            break
    if hdr is None:
        return [], set()

    c_wk  = col_of(hdr, "Tuần")
    c_dt  = col_of(hdr, "Ngày")
    c_ven = col_of(hdr, "Tên Sân")
    c_vs  = col_of(hdr, "Đối thủ")
    c_gf  = col_of(hdr, "Bàn Thắng  Goals For", "Bàn Thắng Goals For", "Goals For")
    c_ga  = col_of(hdr, "Bàn thua Goals Against", "Goals Against")
    c_res = col_of(hdr, "Kết quả")

    M, valid = [], set()
    for row in rows[hdr_i + 1 :]:
        if not row:
            continue
        wk_raw = row[c_wk] if c_wk >= 0 and c_wk < len(row) else ""
        m = re.search(r"\d+", str(wk_raw))
        if not m:
            continue
        wk = int(m.group())

        res_raw = row[c_res] if c_res >= 0 and c_res < len(row) else ""
        gf_raw  = row[c_gf]  if c_gf  >= 0 and c_gf  < len(row) else ""
        ga_raw  = row[c_ga]  if c_ga  >= 0 and c_ga  < len(row) else ""

        # Bỏ qua tuần không có kết quả hoặc điểm số
        result = RESULT_MAP.get(str(res_raw).strip(), "")
        try:
            gf = int(str(gf_raw).strip())
            ga = int(str(ga_raw).strip())
        except (ValueError, TypeError):
            continue  # điểm số chưa nhập → bỏ qua

        if not result:
            result = "W" if gf > ga else ("D" if gf == ga else "L")

        # Ngày: DD/MM/YYYY → DD/MM
        dt_raw = str(row[c_dt]).strip() if c_dt >= 0 and c_dt < len(row) else ""
        parts = dt_raw.split("/")
        dt = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else dt_raw

        ven_raw = str(row[c_ven]).strip() if c_ven >= 0 and c_ven < len(row) else ""
        venue = VENUE_MAP.get(ven_raw, ven_raw)

        vs = str(row[c_vs]).strip() if c_vs >= 0 and c_vs < len(row) else ""
        vs = vs.replace("Sân cáp", "Sân Cáp")
        if not vs or vs in ("-", "Nghỉ"):
            continue

        M.append({"wk": wk, "dt": dt, "vs": vs, "gf": gf, "ga": ga, "r": result, "v": venue})
        valid.add(wk)

    M.sort(key=lambda x: x["wk"])
    return M, valid


# ───────────── TEAM TOTALS ─────────────
def compute_team(M):
    w = sum(1 for m in M if m["r"] == "W")
    d = sum(1 for m in M if m["r"] == "D")
    l = sum(1 for m in M if m["r"] == "L")
    gf = sum(m["gf"] for m in M)
    ga = sum(m["ga"] for m in M)
    form = [m["r"] for m in M[-5:]]
    return {"m": len(M), "w": w, "d": d, "l": l, "gf": gf, "ga": ga, "gd": gf - ga, "form": form}


# ───────────── PARSE GOAL DETAILS ─────────────
def parse_goals(ws, valid):
    if ws is None:
        return {}
    rows = ws.get_all_values()
    hdr, hdr_i = None, 0
    for i, row in enumerate(rows):
        j = " ".join(row)
        if "Hiệp" in j and "Loại bàn thắng" in j:
            hdr, hdr_i = row, i
            break
    if hdr is None:
        return {}

    c_wk  = col_of(hdr, "Tuần")
    c_h   = col_of(hdr, "Hiệp")
    c_sc  = col_of(hdr, "Goals")
    c_as  = col_of(hdr, "Assist")
    c_tp  = col_of(hdr, "Loại bàn thắng")

    MG = {}
    for row in rows[hdr_i + 1 :]:
        wk_raw = row[c_wk] if c_wk >= 0 and c_wk < len(row) else ""
        m = re.search(r"\d+", str(wk_raw))
        if not m:
            continue
        wk = int(m.group())
        if wk not in valid:
            continue

        scorer  = str(row[c_sc]).strip() if c_sc >= 0 and c_sc < len(row) else ""
        assist  = str(row[c_as]).strip() if c_as >= 0 and c_as < len(row) else ""
        tp_raw  = str(row[c_tp]).strip() if c_tp >= 0 and c_tp < len(row) else "Thường"
        h_raw   = str(row[c_h]).strip()  if c_h  >= 0 and c_h  < len(row) else "H1"
        half    = 2 if "H2" in h_raw or h_raw == "2" else 1

        if not scorer:
            continue

        if wk not in MG:
            MG[wk] = {"s": [], "ms": [], "c": [], "pf": 0, "ps": 0}

        if "Pen (Vào)" in tp_raw or "Pen(Vào)" in tp_raw:
            g = {"sc": scorer, "t": "pen", "h": half}
            if assist:
                g["as"] = assist
            MG[wk]["s"].append(g)
        elif "Pen (Hỏng)" in tp_raw or "Pen(Hỏng)" in tp_raw:
            MG[wk]["ms"].append({"sc": scorer, "h": half})
        else:
            g = {"sc": scorer, "t": "normal", "h": half}
            if assist:
                g["as"] = assist
            MG[wk]["s"].append(g)

    return MG


# ───────────── PARSE GK STATS ─────────────
def parse_gk(ws, MG, valid):
    """
    Sheet GK: mỗi hàng = một trận, theo thứ tự giảm dần (tuần gần nhất → tuần xa nhất).
    Cột: Tên thủ môn | Bàn thua H1 | Bàn thua H2 | Tổng bàn thua | Đối mặt Pen | Cản Pen
    """
    if ws is None:
        return MG
    rows = ws.get_all_values()
    hdr, hdr_i = None, 0
    for i, row in enumerate(rows):
        j = " ".join(row)
        if "Tên thủ môn" in j and "Bàn thua H1" in j:
            hdr, hdr_i = row, i
            break
    if hdr is None:
        return MG

    c_gk = col_of(hdr, "Tên thủ môn")
    c_h1 = col_of(hdr, "Bàn thua H1")
    c_h2 = col_of(hdr, "Bàn thua H2")
    c_pf = col_of(hdr, "Đối mặt Pen")
    c_ps = col_of(hdr, "Cản Pen")

    # Sorted weeks, giảm dần (gần nhất trước)
    sorted_wks = sorted(valid, reverse=True)
    data_rows = [r for r in rows[hdr_i + 1 :] if any(r)]

    for idx, wk in enumerate(sorted_wks):
        if idx >= len(data_rows):
            break
        row = data_rows[idx]

        gk = str(row[c_gk]).strip() if c_gk >= 0 and c_gk < len(row) else ""
        if not gk:
            continue  # bỏ qua hàng không có tên thủ môn

        def safe_int(col):
            if col < 0 or col >= len(row):
                return 0
            try:
                return int(str(row[col]).strip() or "0")
            except ValueError:
                return 0

        h1 = safe_int(c_h1)
        h2 = safe_int(c_h2)
        pf = safe_int(c_pf)
        ps = safe_int(c_ps)

        if h1 == 0 and h2 == 0 and pf == 0:
            continue  # không có dữ liệu thực

        if wk not in MG:
            MG[wk] = {"s": [], "ms": [], "c": [], "pf": 0, "ps": 0}

        MG[wk]["c"] = (
            [{"gk": gk, "h": 1}] * h1 + [{"gk": gk, "h": 2}] * h2
        )
        if pf:
            MG[wk]["pf"] = pf
        if ps:
            MG[wk]["ps"] = ps

    return MG


# ───────────── PARSE PLAYERS ─────────────
def parse_players(ws, M, valid):
    rows = ws.get_all_values()
    hdr, hdr_i = None, 0
    for i, row in enumerate(rows):
        j = " ".join(row)
        if "Biệt danh" in j and "Vị trí" in j and "Goals" in j:
            hdr, hdr_i = row, i
            break
    if hdr is None:
        return [], {}

    c_name  = col_of(hdr, "Họ và tên")
    c_nick  = col_of(hdr, "Biệt danh")
    c_pos   = col_of(hdr, "Vị trí")
    c_no    = col_of(hdr, "Số áo")
    c_goals = col_of(hdr, "Goals")

    # Bản đồ: số tuần → chỉ số cột trong header
    week_cols = {}
    for j, h in enumerate(hdr):
        m = re.match(r"Tuần\s*(\d+)$", str(h).strip())
        if m:
            week_cols[int(m.group(1))] = j

    # Bản đồ: tuần → chỉ số trong M
    wk2idx = {m["wk"]: i for i, m in enumerate(M)}
    total_m = len(M)

    P, PM = [], {}

    for row in rows[hdr_i + 1 :]:
        if not row or all(not c for c in row):
            continue
        tt = str(row[0]).strip()
        if not tt or not tt.isdigit():
            continue  # bỏ hàng tổng kết / tiêu đề phụ

        full = str(row[c_name]).strip() if c_name >= 0 and c_name < len(row) else ""
        nick = str(row[c_nick]).strip() if c_nick >= 0 and c_nick < len(row) else ""
        pos  = str(row[c_pos]).strip()  if c_pos  >= 0 and c_pos  < len(row) else "MF"
        no   = str(row[c_no]).strip()   if c_no   >= 0 and c_no   < len(row) else ""

        display = nick or full
        display = DISPLAY_NAME_MAP.get(display, display)
        if not display:
            continue

        try:
            goals = int(str(row[c_goals]).strip() or "0") if c_goals >= 0 and c_goals < len(row) else 0
        except ValueError:
            goals = 0

        # Xây dựng mảng PM và tính thống kê từ cột tuần
        pm_arr = [None] * total_m
        p_m = p_w = p_d = p_l = p_gf = p_ga = 0

        for wk_num, col_j in week_cols.items():
            if wk_num not in valid or wk_num not in wk2idx:
                continue
            if col_j >= len(row):
                continue
            val = str(row[col_j]).strip()
            if val.upper() == "TRUE":
                played, g_count = True, 0
            elif val.upper() in ("FALSE", "-", ""):
                played = False
                g_count = 0
            else:
                try:
                    g_count = int(val)
                    played = True
                except ValueError:
                    played = False
                    g_count = 0

            if not played:
                continue

            idx = wk2idx[wk_num]
            pm_arr[idx] = g_count
            match = M[idx]
            p_m += 1
            p_gf += match["gf"]
            p_ga += match["ga"]
            if match["r"] == "W":
                p_w += 1
            elif match["r"] == "D":
                p_d += 1
            else:
                p_l += 1

        if p_m == 0:
            continue

        # 5 trận gần nhất (chỉ tính trận có kết quả)
        fa = []
        for match in reversed(M):
            col_j = week_cols.get(match["wk"], -1)
            if col_j < 0 or col_j >= len(row):
                continue
            val = str(row[col_j]).strip()
            if val.upper() == "TRUE":
                played = True
            elif val.upper() in ("FALSE", "-", ""):
                played = False
            else:
                try:
                    int(val)
                    played = True
                except ValueError:
                    played = False
            fa.append(match["r"] if played else "N")
            if len(fa) == 5:
                break
        fa.reverse()
        while len(fa) < 5:
            fa.insert(0, "N")

        mp = round(p_m / total_m, 4) if total_m else 0
        wp = round(p_w / p_m, 4) if p_m else 0
        ptype = "main" if mp >= 0.25 else "sub"

        P.append({
            "n": display, "p": pos, "no": no,
            "g": goals, "m": p_m, "mp": mp, "wp": wp,
            "fa": fa, "w": p_w, "d": p_d, "l": p_l,
            "gf": p_gf, "ga": p_ga, "gd": p_gf - p_ga,
            "t": ptype,
        })
        PM[display] = pm_arr

    return P, PM


# ───────────── GENERATE JS ─────────────
def generate_js(T, M, MG, P, PM):
    today = datetime.date.today().strftime("%d/%m/%Y")
    earliest_mg = min(MG.keys()) if MG else 21

    # T
    form_js = "[" + ",".join(f'"{f}"' for f in T["form"]) + "]"
    t_js = f'{{m:{T["m"]},gf:{T["gf"]},ga:{T["ga"]},gd:{T["gd"]},w:{T["w"]},d:{T["d"]},l:{T["l"]},form:{form_js}}}'

    # M
    m_rows = []
    for m in M:
        m_rows.append(
            f'  {{wk:{m["wk"]},dt:"{m["dt"]}",vs:"{m["vs"]}",gf:{m["gf"]},ga:{m["ga"]},r:"{m["r"]}",v:"{m["v"]}"}}'
        )
    m_js = "[\n" + ",\n".join(m_rows) + "\n]"

    # MG
    mg_entries = []
    for wk in sorted(MG):
        mg = MG[wk]
        s_js = "[" + ",".join(
            "{" + f'sc:"{g["sc"]}"' + (f',as:"{g["as"]}"' if g.get("as") else "") + f',t:"{g["t"]}",h:{g["h"]}' + "}"
            for g in mg.get("s", [])
        ) + "]"
        ms_js = "[" + ",".join(
            "{" + f'sc:"{g["sc"]}",h:{g["h"]}' + "}"
            for g in mg.get("ms", [])
        ) + "]"
        c_js = "[" + ",".join(
            "{" + f'gk:"{c["gk"]}",h:{c["h"]}' + "}"
            for c in mg.get("c", [])
        ) + "]"
        pf = mg.get("pf", 0)
        ps = mg.get("ps", 0)
        entry = f"  {wk}:{{s:{s_js}"
        if mg.get("ms"):
            entry += f",ms:{ms_js}"
        entry += f",c:{c_js},pf:{pf},ps:{ps}}}"
        mg_entries.append(entry)
    mg_js = "{\n" + ",\n".join(mg_entries) + "\n}" if mg_entries else "{}"

    # P
    p_rows = []
    for p in P:
        fa_js = "[" + ",".join(f'"{f}"' for f in p["fa"]) + "]"
        p_rows.append(
            "  {"
            + f'n:"{p["n"]}",p:"{p["p"]}",no:"{p["no"]}",g:{p["g"]},'
            + f'm:{p["m"]},mp:{p["mp"]},wp:{p["wp"]},fa:{fa_js},'
            + f'w:{p["w"]},d:{p["d"]},l:{p["l"]},gf:{p["gf"]},ga:{p["ga"]},gd:{p["gd"]},t:"{p["t"]}"'
            + "}"
        )
    p_js = "[\n" + ",\n".join(p_rows) + "\n]"

    # PM
    pm_items = []
    for name, arr in PM.items():
        vals = ",".join("null" if v is None else str(v) for v in arr)
        pm_items.append(f'"{name}":[{vals}]')
    pm_js = "{" + ",".join(pm_items) + "}"

    # Phần aggregates (JS thuần, không dùng f-string để tránh escape)
    agg_js = (
        "// Compute aggregates\n"
        "const AST_H={},PEN={},HGF={h1:0,h2:0},HGA={h1:0,h2:0},GKD={};\n"
        "Object.values(MG).forEach(mg=>{\n"
        "  (mg.s||[]).forEach(g=>{\n"
        "    if(g.as){if(!AST_H[g.as])AST_H[g.as]={h1:0,h2:0};g.h===1?AST_H[g.as].h1++:AST_H[g.as].h2++;}\n"
        "    if(g.t===\"pen\"){if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].sc++}\n"
        "    g.h===1?HGF.h1++:HGF.h2++;\n"
        "  });\n"
        "  (mg.ms||[]).forEach(g=>{if(!PEN[g.sc])PEN[g.sc]={sc:0,ms:0};PEN[g.sc].ms++});\n"
        "  (mg.c||[]).forEach(c=>{\n"
        "    if(!GKD[c.gk])GKD[c.gk]={conc:0,h1:0,h2:0,pf:0,ps:0};\n"
        "    GKD[c.gk].conc++;c.h===1?(GKD[c.gk].h1++,HGA.h1++):(GKD[c.gk].h2++,HGA.h2++);\n"
        "  });\n"
        "  if(mg.pf)Object.values(GKD).forEach(d=>{d.pf+=mg.pf;d.ps+=mg.ps||0});\n"
        "});\n"
        "const AST=Object.fromEntries(Object.entries(AST_H).map(([k,v])=>[k,v.h1+v.h2]));\n"
    )

    return (
        f"// ===== CORE DATA =====\n"
        f"// Tự động cập nhật bởi update_stats.py ngày {today}\n"
        f"const T={t_js};\n"
        f"T.pts=T.w*3+T.d; T.ppg=T.pts/T.m;\n\n"
        f"const M={m_js};\n\n"
        f"// ===== GOAL DETAIL (Tuần {earliest_mg}) =====\n"
        f"// s=scored [{{sc,as,t:\"normal\"|\"pen\",h:1|2}}]  ms=missed pen  c=conceded [{{gk,h,t}}]  pf/ps=pen faced/saved\n"
        f"const MG={mg_js};\n\n"
        f"{agg_js}\n"
        f"// ===== PLAYERS =====\n"
        f"const P={p_js};\n\n"
        f"const PM={pm_js};\n"
    ), earliest_mg


# ───────────── UPDATE HTML ─────────────
def update_html(path, data_js, T, earliest_mg):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # Thay thế phần dữ liệu JS
    pattern = r"// ===== CORE DATA =====.*?(?=// ===== RENDERS =====)"
    html = re.sub(pattern, data_js + "\n", html, flags=re.DOTALL)

    # Cập nhật KPI header: số trận
    html = re.sub(
        r'(<div class="kp"><div class="kp-n">)\d+(</div><div class="kp-l">Trận</div></div>)',
        rf"\g<1>{T['m']}\2",
        html,
    )
    # W/D/L record
    html = re.sub(
        r'(<div class="kp"><div class="kp-n sm">)\d+W · \d+D · \d+L(</div><div class="kp-l">Thành tích</div></div>)',
        rf"\g<1>{T['w']}W · {T['d']}D · {T['l']}L\2",
        html,
    )
    # Điểm
    pts = T["w"] * 3 + T["d"]
    html = re.sub(
        r'(<div class="kp"><div class="kp-n or">)\d+(</div><div class="kp-l">Điểm</div></div>)',
        rf"\g<1>{pts}\2",
        html,
    )
    # Subtitle
    html = re.sub(r"(Cập nhật sau )\d+( trận)", rf"\g<1>{T['m']}\2", html)
    html = re.sub(r"(Dữ liệu chi tiết từ tuần )\d+", rf"\g<1>{earliest_mg}", html)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ───────────── MAIN ─────────────
def main():
    print("Kết nối Google Sheets...")
    gc = get_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    sheets = sh.worksheets()
    print(f"Tìm thấy {len(sheets)} sheet: {[w.title for w in sheets]}")

    # Lịch thi đấu
    match_ws = find_ws(sh, "Đối thủ", "Kết quả")
    if not match_ws:
        match_ws = find_ws(sh, "Tên Sân", "Tuần")
    if not match_ws:
        print("LỖI: Không tìm thấy sheet lịch thi đấu!")
        sys.exit(1)
    print(f"→ Lịch thi đấu: '{match_ws.title}'")

    # Cầu thủ
    player_ws = find_ws(sh, "Biệt danh", "Vị trí", "Goals")
    if not player_ws:
        print("LỖI: Không tìm thấy sheet cầu thủ!")
        sys.exit(1)
    print(f"→ Cầu thủ: '{player_ws.title}'")

    # Bàn thắng chi tiết
    goal_ws = find_ws(sh, "Hiệp", "Loại bàn thắng")
    print(f"→ Bàn thắng: '{goal_ws.title if goal_ws else 'Không tìm thấy'}'")

    # Thủ môn
    gk_ws = find_ws(sh, "Tên thủ môn", "Bàn thua H1")
    print(f"→ Thủ môn: '{gk_ws.title if gk_ws else 'Không tìm thấy'}'")

    print("\nĐọc lịch thi đấu...")
    M, valid = parse_matches(match_ws)
    print(f"  {len(M)} trận hợp lệ: {sorted(valid)}")
    if not M:
        print("Không có trận nào! Dừng lại.")
        sys.exit(0)

    T = compute_team(M)
    pts = T["w"] * 3 + T["d"]
    print(f"  Đội: {T['m']}T {T['w']}T {T['d']}H {T['l']}B | GF:{T['gf']} GA:{T['ga']} | {pts} điểm")

    print("Đọc bàn thắng chi tiết...")
    MG = parse_goals(goal_ws, valid)
    print(f"  Dữ liệu cho tuần: {sorted(MG.keys())}")

    print("Đọc thống kê thủ môn...")
    MG = parse_gk(gk_ws, MG, valid)

    print("Đọc dữ liệu cầu thủ...")
    P, PM = parse_players(player_ws, M, valid)
    print(f"  {len(P)} cầu thủ")

    print("Tạo dữ liệu JavaScript...")
    data_js, earliest_mg = generate_js(T, M, MG, P, PM)

    print(f"Cập nhật {STATS_HTML}...")
    update_html(STATS_HTML, data_js, T, earliest_mg)
    print("✓ Xong!")


if __name__ == "__main__":
    main()
