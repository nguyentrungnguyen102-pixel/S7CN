#!/usr/bin/env python3
"""
Auto-update stats.html from Google Sheets data.

Usage:
  python3 scripts/update_stats.py

Requirements:
  - Google Sheet must be set to "Anyone with link can view"
  - Sheet ID configured in SHEET_ID below
  - Run from repo root
"""

import csv
import io
import json
import re
import sys
import urllib.request
from datetime import datetime

SHEET_ID = "1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68"
STATS_HTML = "stats.html"

# Tab GIDs (from Google Sheets URL ?gid=...)
GID_STATS = 602325894   # Tab chứa thống kê cầu thủ + danh sách trận

POSITION_MAP = {
    "Tiền vệ": "CM", "Tiền đạo": "ST", "Hậu vệ": "CB",
    "Thủ môn": "GK", "Trung vệ": "CB", "Hậu vệ trái": "LB",
    "Hậu vệ phải": "RB", "Tiền vệ trái": "LM", "Tiền vệ phải": "RM",
    "Cánh trái": "LW", "Cánh phải": "RW",
}

RESULT_MAP = {"Thắng": "W", "Hòa": "D", "Thua": "L", "Nghỉ": None}


def fetch_csv(gid):
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={gid}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8-sig")
    except Exception as e:
        print(f"ERROR fetching sheet (gid={gid}): {e}")
        print("Make sure the Google Sheet is set to 'Anyone with link can view'")
        sys.exit(1)


def parse_stats_csv(raw_csv):
    """Parse the main stats tab CSV into structured data."""
    rows = list(csv.reader(io.StringIO(raw_csv)))

    matches = []         # M array
    players = []         # P array
    team = {}            # T object
    match_goals = {}     # MG object (raw event rows)
    pm_data = {}         # PM matrix: {player: [goals_per_match]}

    # --- Find key sections by scanning header rows ---
    match_hdr_idx = None
    player_hdr_idx = None
    summary_idx = None

    for i, row in enumerate(rows):
        row_str = ",".join(row)
        if "Đối thủ" in row_str and "GF" in row_str and "Kết quả" in row_str and match_hdr_idx is None:
            match_hdr_idx = i
        if "Biệt danh" in row_str and "Goals" in row_str and "Rating" in row_str:
            player_hdr_idx = i
        if "Tổng trận" in row_str and "Thắng" in row_str and summary_idx is None:
            summary_idx = i

    # --- Parse team summary ---
    if summary_idx is not None:
        for r in rows[summary_idx:summary_idx + 30]:
            row_str = ",".join(r)
            if "Tổng trận" in row_str:
                vals = [c for c in r if c.strip()]
                if len(vals) >= 2:
                    try:
                        team["m"] = int(vals[-1])
                    except ValueError:
                        pass
            if "Thắng" in row_str and len([c for c in r if c.strip()]) == 2:
                vals = [c for c in r if c.strip()]
                try:
                    team["w"] = int(vals[-1])
                except ValueError:
                    pass
            if "GF" in row_str and len([c for c in r if c.strip()]) == 2:
                vals = [c for c in r if c.strip()]
                try:
                    team["gf"] = int(vals[-1])
                except ValueError:
                    pass
            if "GA" in row_str and len([c for c in r if c.strip()]) == 2:
                vals = [c for c in r if c.strip()]
                try:
                    team["ga"] = int(vals[-1])
                except ValueError:
                    pass

    # --- Parse match list ---
    if match_hdr_idx is not None:
        hdr = rows[match_hdr_idx]
        col = {h.strip(): i for i, h in enumerate(hdr) if h.strip()}

        def c(row, key, default=""):
            idx = col.get(key)
            return row[idx].strip() if idx is not None and idx < len(row) else default

        for row in rows[match_hdr_idx + 1:]:
            if not any(row):
                continue
            week_raw = c(row, "Tuần")
            if not week_raw or not week_raw.replace("Tuần", "").strip().isdigit():
                continue
            wk = int(week_raw.replace("Tuần", "").strip())
            result_vi = c(row, "Kết quả")
            result = RESULT_MAP.get(result_vi)
            if result is None:  # rest week
                continue

            date_raw = c(row, "Ngày")
            date_str = date_raw[:-5] if len(date_raw) > 5 else date_raw  # strip year
            try:
                dt = datetime.strptime(date_raw, "%d/%m/%Y")
                date_str = dt.strftime("%d/%m")
            except ValueError:
                pass

            try:
                gf = int(c(row, "GF") or 0)
                ga = int(c(row, "GA") or 0)
            except ValueError:
                continue

            opponent = c(row, "Đối thủ")
            venue = c(row, "SVĐ")

            matches.append({
                "wk": wk,
                "dt": date_str,
                "vs": opponent,
                "gf": gf,
                "ga": ga,
                "r": result,
                "v": venue,
            })

    matches.sort(key=lambda x: x["wk"])

    # --- Parse player stats table ---
    if player_hdr_idx is not None:
        hdr = rows[player_hdr_idx]
        col = {h.strip(): i for i, h in enumerate(hdr) if h.strip()}

        def pc(row, key, default="0"):
            idx = col.get(key)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip().replace(",", ".") or default

        total_m = team.get("m", len(matches))

        for row in rows[player_hdr_idx + 2:]:  # skip separator row
            name = row[0].strip() if row else ""
            if not name or name.startswith("|") or name.startswith(":-"):
                continue
            try:
                m = int(pc(row, "Match", "0"))
            except ValueError:
                continue
            if m == 0:
                continue

            try:
                w = int(pc(row, "Thắng", "0"))
                d = int(pc(row, "Hòa", "0"))
                l = int(pc(row, "Thua", "0"))
                gf = int(pc(row, "GF", "0"))
                ga = int(pc(row, "GA", "0"))
                goals = int(pc(row, "Goals", "0"))
                pos = pc(row, "Vị trí", "CM")
            except ValueError:
                continue

            mp = round(m / max(total_m, 1), 2)
            wp = round(w / max(m, 1), 4)
            gd = gf - ga
            ppg = round((w * 3 + d) / max(m, 1), 4)
            t_type = "sub" if m < total_m * 0.3 else "main"

            players.append({
                "n": name,
                "p": pos,
                "no": "",
                "g": goals,
                "m": m,
                "mp": mp,
                "wp": wp,
                "fa": ["N", "N", "N", "N", "N"],
                "w": w,
                "d": d,
                "l": l,
                "gf": gf,
                "ga": ga,
                "gd": gd,
                "t": t_type,
            })

    # Build simplified team object
    m_count = team.get("m", len(matches))
    w_count = team.get("w", sum(1 for m in matches if m["r"] == "W"))
    d_count = sum(1 for m in matches if m["r"] == "D")
    l_count = sum(1 for m in matches if m["r"] == "L")
    gf_total = team.get("gf", sum(m["gf"] for m in matches))
    ga_total = team.get("ga", sum(m["ga"] for m in matches))
    pts = w_count * 3 + d_count
    ppg = round(pts / max(m_count, 1), 2)

    team_obj = {
        "n": "LAIRAI FC",
        "m": m_count,
        "w": w_count,
        "d": d_count,
        "l": l_count,
        "gf": gf_total,
        "ga": ga_total,
        "gd": gf_total - ga_total,
        "pts": pts,
        "ppg": ppg,
    }

    return team_obj, matches, players, match_goals, pm_data


def format_js_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        return "[" + ",".join(format_js_value(x) for x in v) + "]"
    if isinstance(v, dict):
        pairs = ",".join(f'"{k}":{format_js_value(v2)}' for k, v2 in v.items())
        return "{" + pairs + "}"
    return str(v)


def build_T_line(team):
    return (
        f'const T={{n:"{team["n"]}",m:{team["m"]},w:{team["w"]},'
        f'd:{team["d"]},l:{team["l"]},gf:{team["gf"]},ga:{team["ga"]},'
        f'gd:{team["gd"]},pts:{team["pts"]},ppg:{team["ppg"]}}};'
    )


def build_M_lines(matches):
    lines = ["const M=["]
    for m in matches:
        lines.append(
            f'  {{wk:{m["wk"]},dt:"{m["dt"]}",vs:"{m["vs"]}",'
            f'gf:{m["gf"]},ga:{m["ga"]},r:"{m["r"]}",v:"{m["v"]}"}},',
        )
    lines.append("];")
    return "\n".join(lines)


def build_P_lines(players):
    lines = ["const P=["]
    for p in players:
        fa = json.dumps(p["fa"])
        lines.append(
            f'  {{n:"{p["n"]}",p:"{p["p"]}",no:"{p["no"]}",'
            f'g:{p["g"]},m:{p["m"]},mp:{p["mp"]},wp:{p["wp"]},'
            f'fa:{fa},w:{p["w"]},d:{p["d"]},l:{p["l"]},'
            f'gf:{p["gf"]},ga:{p["ga"]},gd:{p["gd"]},t:"{p["t"]}"}},',
        )
    lines.append("];")
    return "\n".join(lines)


def update_html(html, team, matches, players):
    """Replace data sections in stats.html."""
    # Replace T
    t_pattern = r'const T=\{[^}]+\};'
    new_T = build_T_line(team)
    html, n = re.subn(t_pattern, new_T, html, count=1)
    print(f"  T updated: {n} replacement(s)")

    # Replace M
    m_pattern = r'const M=\[[^\]]*(?:\[[^\]]*\][^\]]*)*\];'
    new_M = build_M_lines(matches)
    html, n = re.subn(m_pattern, new_M, html, count=1, flags=re.DOTALL)
    print(f"  M updated: {n} replacement(s)")

    # Replace P
    p_pattern = r'const P=\[.*?\];'
    new_P = build_P_lines(players)
    html, n = re.subn(p_pattern, new_P, html, count=1, flags=re.DOTALL)
    print(f"  P updated: {n} replacement(s)")

    return html


def main():
    print(f"Fetching stats tab (gid={GID_STATS})...")
    raw = fetch_csv(GID_STATS)
    print(f"  Got {len(raw)} bytes")

    print("Parsing data...")
    team, matches, players, mg, pm = parse_stats_csv(raw)
    print(f"  Team: {team['m']} matches, {team['w']}W/{team['d']}D/{team['l']}L")
    print(f"  Matches parsed: {len(matches)}")
    print(f"  Players parsed: {len(players)}")

    print(f"Reading {STATS_HTML}...")
    with open(STATS_HTML, encoding="utf-8") as f:
        html = f.read()

    print("Updating HTML...")
    html = update_html(html, team, matches, players)

    with open(STATS_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {STATS_HTML} saved.")


if __name__ == "__main__":
    main()
