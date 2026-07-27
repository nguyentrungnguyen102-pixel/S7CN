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

## Data quirks đã biết (đừng điều tra lại mỗi tuần)

- `T.gf` = 71 nhưng tổng bàn theo cầu thủ = 70 → 1 bàn không quy được cho ai (tuần 14 thiếu 1 dòng `Bàn thắng` trong sheet).
- Tuần 28: cột `GA` ghi 6 nhưng log có 7 dòng `Bàn thua` → lấy theo cột `GF/GA` làm chuẩn.
- `Khanh` chưa có vị trí trong sheet `Info`.
- 3 người trong roster có 0 trận nên không lên bảng: `Văn Tới`, `An`, `Tuấn`.
- Tuần 1–20 không có dữ liệu hiệp và kiến tạo; chỉ từ tuần 21 trở đi mới có.
