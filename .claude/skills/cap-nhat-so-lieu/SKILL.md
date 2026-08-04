---
name: cap-nhat-so-lieu
description: Cập nhật số liệu bóng đá LAIRAI FC từ Google Sheet lên stats.html rồi deploy. Dùng khi anh Nguyên nói "check số liệu", "cập nhật số liệu", "cập nhật tuần N", "chạy lại số liệu", hoặc đưa link Google Sheet của đội.
---

# Cập nhật số liệu LAIRAI FC

Quy trình 6 bước, làm tuần tự, không nhảy bước. Phân công: **Opus lập kế hoạch và kiểm tra, Sonnet thực thi.**

## Bước 1 — Lấy sheet

- Sheet ID: `1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68`
- Gọi `mcp__Google_Drive__download_file_content` với `exportMimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`.
- Kết quả là base64 trong payload JSON `{content,...}`. Nếu file lớn, tool ghi ra file và trả về đường dẫn — decode bằng `base64.b64decode`, lưu thành `.xlsx`, rồi đọc bằng `openpyxl(data_only=True)`.

⚠️ **Cảnh báo quan trọng:**
| Không được làm | Vì sao |
|---|---|
| Dùng `mcp__Google_Drive__read_file_content` | Âm thầm cắt cụt ở ~2.500 ô/sheet, làm mất "Log tuần" từ Tuần 15 trở đi, không báo lỗi |
| Fetch URL export CSV (`docs.google.com/.../export?format=csv`) | Proxy sandbox chặn, trả `http 000` |

6 lần automation trước trong repo này đã fail đúng vì lý do trên, để lại các branch `claude/kind-gates-*` đã bị bỏ.

## Bước 2 — Dựng lại dữ liệu

```
python3 scripts/rebuild_data.py --xlsx <đường dẫn xlsx>
```

- Script này regenerate toàn bộ `M`, `PM`, `P`, `MG` trong `stats.html` từ sheet.
- **Không bao giờ sửa tay số liệu trong `stats.html`** — đây chính là nguyên nhân của mọi lỗi trước đây.

Nguồn dữ liệu:
- Sheet **`Log tuần`**: mỗi dòng là 1 sự kiện — `Điểm danh` / `Bàn thắng` / `Bàn thua` / `Nghỉ`.
- Sheet **`Info`**: roster — `TT` là số (chính thức) → `t:"main"`; `TT` là chữ `Sub` → `t:"sub"`.
- Quy tắc điểm danh ngầm định: cầu thủ được ghi nhận là người ghi bàn, kiến tạo, hoặc thủ môn trong tuần đó thì tính là có mặt, dù không có dòng `Điểm danh`.

## Bước 3 — Kiểm tra

```
python3 scripts/check_stats.py --xlsx <đường dẫn xlsx>
```

- Phải exit 0.
- `[WARN]` chấp nhận được (báo lỗ hổng dữ liệu sheet để anh tự sửa).
- Có `[FAIL]` thì phải xử lý xong mới đi tiếp.

## Bước 4 — Commit & push

- Push thẳng lên `main`. Repo này deploy từ `main` duy nhất, không có branch tính năng (chủ ý thiết kế).

## Bước 5 — Deploy

- Vercel project `s7cn`, team `nguyennt102`, project id `prj_0AMCUSgmUwDkFDAR9ievquRiTkoH`.
- Dùng `mcp__Vercel__deploy_to_vercel`.
- Netlify **không dùng nữa** — đã hết quota, config đã xóa. Không đề xuất lại Netlify.

## Bước 6 — Xác minh production (bắt buộc)

- Fetch URL đã deploy bằng `mcp__Vercel__web_fetch_vercel_url`, xác nhận trang thật sự hiển thị số liệu mới:
  - hero KPI (số trận / W·D·L / điểm)
  - tuần mới nhất trong danh sách trận
- `WebFetch` và `curl` thường bị proxy chặn (403) — chỉ tool trên mới dùng được.
- **Chỉ báo "xong" sau khi bước này pass.** Anh Nguyên đã nhiều lần nhận việc chưa được verify — bước này tồn tại để chặn việc đó, không được bỏ qua.

## Những khối KHÔNG do script sinh — đừng đụng

| Khối | Nguồn | Ghi chú |
|---|---|---|
| `const M25=[...]` | sheet `Thống kê 2025`, lọc `Sân 11` | Dữ liệu lịch sử mùa 2025 cho phần so sánh. Script **không** sinh khối này và `find_block` khớp chính xác `^const M=` nên không đụng tới. Mùa 2025 đã đóng, không cần cập nhật. |
| Link xem lại (`lv`) | cột **O** sheet `Thống kê match` | Từ nay `rebuild_data.py` **có** đọc. Trước đây thì không — chạy script sẽ xoá sạch link mà không báo gì. |

**Chốt chặn link xem lại:** nếu script thấy link đang có trong `stats.html` mà sheet không cho ra, nó **dừng lại, không ghi gì** và in cảnh báo. Gần như luôn có nghĩa là file xlsx đang dùng cũ hơn sheet thật — tải lại sheet rồi chạy lại. Chỉ dùng `--force` sau khi đã đối chiếu cột O bằng mắt.

Tương tự, nếu `check_stats.py --xlsx` báo `[FAIL]` mục 9 mà **toàn bộ** khác biệt nằm ở `lv`, đó là dấu hiệu xlsx cũ chứ không phải lỗi dữ liệu.

## Data quirks đã biết (đừng điều tra lại mỗi tuần)

- ~~`T.gf` = 71 nhưng tổng bàn theo cầu thủ = 70 (tuần 14 thiếu 1 dòng `Bàn thắng`)~~ — **đã hết từ tuần 31**: sheet đã bổ sung dòng đó, ghi cho `Bạn mới`. Tổng khớp 74 = 74.
- ~~Tuần 28: cột `GA` ghi 6 nhưng log có 7 dòng `Bàn thua`~~ — **đã hết từ tuần 31**, sheet đã sửa khớp.
- ~~`Khanh` chưa có vị trí trong sheet `Info`~~ — **đã hết từ tuần 31**: `Info` giờ ghi `Khánh bạn Duyên`, vị trí LB.
- `Khanh` (không dấu, tuần 30) và `Khánh` (có dấu, tuần 31) trong `Log tuần` là **một người**. Đã gộp bằng `DISPLAY` trong `rebuild_data.py`. Nếu sheet còn gõ lệch dấu tên khác, thêm alias vào đó chứ đừng sửa tay `stats.html`.
- `Bạn mới` (ghi bàn tuần 14) chỉ có trong `Log tuần`, chưa có dòng trong `Info`. Script tự thêm vào cuối roster dạng sub và in `[WARN]` — chấp nhận được, nhưng nếu biết tên thật thì bổ sung vào `Info`.
- 3 người trong roster có 0 trận nên không lên bảng: `Văn Tới`, `An`, `Tuấn`.
- Tuần 1–20 không có dữ liệu hiệp và kiến tạo; chỉ từ tuần 21 trở đi mới có.
