---
name: cap-nhat-so-lieu
description: Cập nhật số liệu bóng đá LAIRAI FC từ Google Sheet lên stats.html rồi deploy. Dùng khi anh Nguyên nói "check số liệu", "cập nhật số liệu", "cập nhật tuần mới", "cập nhật tuần N", "chạy lại số liệu", hoặc đưa link Google Sheet của đội.
---

# Cập nhật số liệu LAIRAI FC

Quy trình 6 bước, làm tuần tự, không nhảy bước. Phân công: **Opus lập kế hoạch và kiểm tra, Sonnet thực thi.**
Thay đổi giao diện/cách tính (không phải cập nhật tuần thường lệ): **trình plan cho anh duyệt trước rồi mới làm.**

## Bước 1 — Lấy sheet

- Sheet ID: `1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68`
- Gọi `mcp__Google_Drive__download_file_content` với `exportMimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`.
- Kết quả quá lớn nên tool ghi ra file JSON `{content,...}` — decode `base64.b64decode(content)` ra `.xlsx` trong **một thư mục riêng** trong scratchpad, đọc bằng `openpyxl.load_workbook(..., data_only=True)`, chạy Python với `-I`.
- Cài openpyxl bằng `python3 -m pip install openpyxl` — `pip` trần có thể trỏ sang Python khác (đã gặp: pip 3.13, python3 là 3.11).

⚠️ **Không được làm:**
| Không được làm | Vì sao |
|---|---|
| Dùng `mcp__Google_Drive__read_file_content` | Âm thầm cắt cụt ở ~2.500 ô/sheet, làm mất "Log tuần" từ Tuần 15 trở đi, không báo lỗi |
| Fetch URL export CSV (`docs.google.com/.../export?format=csv`) | Proxy sandbox chặn, trả `http 000` |
| Load xlsx **không** kèm `data_only=True` rồi `save()` | openpyxl không tính lại công thức → mất sạch giá trị cache của sheet `Thống kê match` (mất cả link xem lại) |

**Trước khi dựng dữ liệu, nhìn nhanh các tuần mới nhất** (số dòng mỗi tuần + `Loại sân`). Đã từng gặp: anh nhập nhầm khiến cả một tuần cũ bị reset về `Nghỉ`, hoặc trận mới bị gắn nhầm số tuần. Thấy bất thường → hỏi anh, đừng chạy `--force`.

## Bước 2 — Dựng lại dữ liệu

```
python3 scripts/rebuild_data.py --xlsx <đường dẫn xlsx>
```

- Script regenerate toàn bộ `M`, `M7`, `PM`, `P`, `MG` trong `stats.html` từ sheet.
- **Không bao giờ sửa tay số liệu trong `stats.html`** — đây là nguyên nhân của mọi lỗi trước đây. Sheet sai thì nhờ anh sửa sheet; cần vá gấp thì vá **bản xlsx nháp cục bộ** rồi chạy script (vẫn qua đủ kiểm tra).

Nguồn dữ liệu:
- Sheet **`Log tuần`**: mỗi dòng là 1 sự kiện — `Điểm danh` / `Bàn thắng` / `Bàn thua` / `Cản Pen` / `Nghỉ`.
- Sheet **`Info`**: roster — `TT` là số → chính thức (`t:"main"`); `TT` là `Sub` → `t:"sub"`. Script quét đến hết sheet, bỏ qua dòng không có Biệt danh (dòng trống lẻ chen giữa không còn làm rơi người phía sau).
- Điểm danh ngầm định: ai ghi bàn, kiến tạo, bắt chính hoặc cản pen trong tuần thì tính là có mặt dù thiếu dòng `Điểm danh`.

**Chỉ Sân 11 được tính.** Tuần có `Loại sân` ≠ `Sân 11` (vd Sân 7) bị loại khỏi `M/PM/P/MG`, script in rõ tuần nào bị loại, `check_stats` báo `[WARN]`. Các trận này vào khối riêng `M7` → thẻ "Sân khác · tham khảo" ở mục Trận đấu, **không tính vào bất kỳ số liệu nào**.

**Loại bàn** (so khớp không phân biệt hoa/thường):
- Bàn thắng: `Thường` / `Pen (Vào)` / `Sút phạt`.
- Bàn thua: **để trống = bàn thường**; thua do pen anh ghi **`Pen`** (script nhận cả `Pen (Vào)`). Không đánh dấu thì không suy luận được.
- `Cản Pen`: cột "Kiến tạo/Thủ môn" là thủ môn, "Loại bàn" là `Pen (Cản)` → `MG[tuần].ps`.
- `pf`/`ps` mỗi thủ môn và **sạch lưới** được tính lúc chạy trong `stats.html`, không có số cứng nào để sửa.

## Bước 3 — Kiểm tra

```
python3 scripts/check_stats.py --xlsx <đường dẫn xlsx>
```

- Phải exit 0. Có `[FAIL]` thì xử lý xong mới đi tiếp. `[WARN]` chấp nhận được (lỗ hổng dữ liệu sheet để anh tự sửa).
- **Mục 10 — vị trí lạ**: sheet `Info` có mã vị trí chưa khai báo trong bảng `POS` của `stats.html` → `[WARN]`. Gặp cảnh báo này thì **phải thêm mã vào `POS`** (xem mục Vị trí bên dưới), nếu không cầu thủ đó mất màu, lọt khỏi bộ lọc tuyến và không bao giờ vào đội hình tiêu biểu.

## Bước 4 — Commit & push

- Push lên `main` (`git push origin HEAD:main` — **không** dùng `git push origin main` khi đang đứng ở branch khác, nó đẩy branch `main` cục bộ đã cũ và bị từ chối). Đồng thời push cùng commit lên branch làm việc được chỉ định.

## Bước 5 — Deploy

- Project Vercel `s7cn` nối thẳng GitHub: **push lên `main` là tự deploy production**, không cần `deploy_to_vercel`.
- Xác nhận bằng `mcp__Vercel__list_deployments` (project `prj_0AMCUSgmUwDkFDAR9ievquRiTkoH`, team `nguyennt102`, `since` = lúc push): bản `target:"production"` phải `READY` và đúng SHA vừa push.
- Netlify **không dùng nữa** — đã hết quota. Không đề xuất lại.

## Bước 6 — Xác minh production (bắt buộc)

1. `curl -s -o <scratchpad>/prod.html https://s7cn.vercel.app/stats.html` → HTTP 200 và `diff -q` khớp byte-for-byte với `stats.html` vừa build.
2. Render bản production bằng Playwright (`playwright-core`, `executablePath:'/opt/pw-browsers/chromium'`), bắt cả `pageerror` lẫn `console.error` (mỗi khối render lỗi bị nuốt, chỉ log ra console). Kiểm tra:
   - hero KPI (số trận / W·D·L / điểm) và tuần mới nhất đứng đầu danh sách trận;
   - **giả lập điện thoại** (`devices['Pixel 7']`): mọi trận có link xem lại đều hiện nút ▶ LIVE khi danh sách đang thu gọn, không tràn ngang;
   - trận sân khác không lẫn vào danh sách chính.
   Lỗi `ERR_TUNNEL_CONNECTION_FAILED` trong console là do sandbox không tải được font/CDN — bỏ qua.
3. **Chỉ báo "xong" sau khi bước này pass.**

## Vị trí — một bảng duy nhất

`const POS={...}` ngay đầu script trong `stats.html` là **nguồn duy nhất**: mỗi mã có nhóm `g` (FW/MF/DF/GK → màu, bộ lọc tuyến, giải thưởng) và `slot` (ô trên sơ đồ đội hình tiêu biểu). Mọi chỗ khác gọi `posGrp()` / `posSlot()`, không được viết lại danh sách mã ở chỗ khác.

| Nhóm | Mã |
|---|---|
| GK | GK |
| DF | CB, DF, LB, LWB, RB, RWB |
| MF | CM, MF, DM, CDM, AM, CAM (ô giữa) · LM (cánh trái) · RM (cánh phải) |
| FW | LW, RW, ST, CF, FW |

Anh thêm mã mới vào sheet → `check_stats` mục 10 báo → thêm 1 dòng vào `POS` (và tên tiếng Việt vào `POSVI`).

## Vinh danh — 5 hạng mục, cách tính

MVP / Hậu vệ / Tiền vệ chỉ xét cầu thủ **chính thức ra sân ≥ 50% số trận** (`AW_MIN_MP`). Mỗi chỉ số quy về 0–1 trong nhóm đủ điều kiện rồi cộng trọng số. Kiến tạo chỉ có từ tuần 21 nên chia cho số trận có dữ liệu chi tiết.

| Giải | Cách tính |
|---|---|
| MVP | 35% (bàn + kiến tạo)/trận · 30% PPG · 20% chuyên cần · 15% bàn thua/trận khi có mặt (thấp là tốt) |
| Vua phá lưới | Nhiều bàn nhất, xét cả sub; bằng bàn thì ít trận hơn xếp trên |
| Iron Man | Nhiều trận nhất, xét cả sub |
| Hậu vệ xuất sắc | Nhóm DF · 40% bàn thua/trận (thấp là tốt) · 25% PPG · 20% chuyên cần · 15% tỉ lệ sạch lưới |
| Tiền vệ xuất sắc | Nhóm MF · 45% (bàn + kiến tạo)/trận · 30% PPG · 25% chuyên cần |

Bảng "Win Impact" ở mục Phân tích **cố ý** giữ công thức riêng (chuyên cần × win × PPG — "ai đá nhiều, thắng nhiều"), không phải MVP.

## Những khối KHÔNG do script sinh — đừng đụng

| Khối | Nguồn | Ghi chú |
|---|---|---|
| `const M25=[...]` | sheet `Thống kê 2025`, lọc `Sân 11` | Lịch sử mùa 2025 cho phần so sánh. Mùa đã đóng. `find_block` khớp chính xác `^const M=` nên không đụng tới (cũng không đụng `M7`). |
| `const POS={...}`, `POSVI` | tay | Sửa khi có mã vị trí mới (xem trên). |

## Link xem lại (`lv`)

- Nguồn: cột **O** sheet `Thống kê match`; chỉ nhận hàng có Kết quả Thắng/Hòa/Thua. Link thiếu `https://` được tự thêm.
- **Chốt chặn:** link đang có trong `stats.html` mà sheet không cho ra → script **dừng, không ghi gì**. Gần như luôn là xlsx cũ — tải lại sheet rồi chạy lại. Chỉ `--force` sau khi đối chiếu cột O bằng mắt. `check_stats` mục 9 FAIL mà toàn bộ khác biệt nằm ở `lv` cũng là dấu hiệu xlsx cũ.
- Anh gửi link qua chat: **không** có tool ghi Google Sheets → nhờ anh dán vào cột O rồi chạy lại. Đừng vá tay `lv` vào `stats.html` (check FAIL và lần sau chốt chặn đứng lại).
- Hiển thị: trận có link gắn `data-keep="1"` nên **luôn hiện khi danh sách thu gọn trên điện thoại**; đầu thẻ có dòng "▶ N trận có video xem lại".

## Data quirks đã biết (đừng điều tra lại mỗi tuần)

- `Khanh` (T30) và `Khánh` là một người — gộp bằng `DISPLAY` trong `rebuild_data.py`. Sheet gõ lệch tên khác thì thêm alias vào đó.
- `Bạn mới` (ghi bàn T14) chưa có dòng trong `Info` → tự thêm dạng sub + `[WARN]`. Biết tên thật thì bổ sung `Info`.
- 3 người roster có 0 trận nên không lên bảng: `Văn Tới`, `An`, `Tuấn`.
- Tuần 1–20 không có dữ liệu hiệp và kiến tạo; chỉ từ tuần 21.
- Trận sạch lưới không có dòng "Bàn thua" nên thủ môn được suy ra từ người có vị trí GK có mặt; nếu ≥2 thủ môn cùng có mặt thì chỉ tính vào tổng đội.

## Lịch sử lỗi đã sửa (để không lặp lại)

- T31: script bỏ qua `Cản Pen`, `pf/ps` luôn 0 và cộng dồn nhầm mọi thủ môn → đã sửa.
- T31: KPI hero lệch trên Android thật do thiếu `text-size-adjust:100%` (headless không tái hiện được) → đã thêm. Anh còn thấy lệch thì xin ảnh chụp thật.
- T31: nhãn `Pen` (bàn thua) và link thiếu `https://` bị bỏ qua → đã sửa.
- T36: trận Sân 7 lẫn vào Log tuần, script chưa lọc theo sân → thêm chốt lọc Sân 11 + khối `M7`.
- T36: `Sút Phạt` viết hoa không khớp → so khớp không phân biệt hoa/thường.
- T38: dòng trống lẻ trong `Info` làm rơi `Hoàng Đại` → `load_roster()` không dừng ở dòng trống nữa.
- T42: vị trí `AM`/`RM` không có màu, Tài Ba (AM) không bao giờ vào đội hình tiêu biểu do ánh xạ vị trí rải rác 9 chỗ → gom về `POS`; Vinh danh tính lại (MVP trước đây tính win% 2 lần và bỏ qua bàn thắng; Hậu vệ trao cho người 6 trận); link xem lại bị ẩn trên mobile khi thu gọn → luôn hiện.
