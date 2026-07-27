# S7CN - LAIRAI FC

Bảng thống kê đội bóng LAIRAI FC mùa giải 2026. Một file HTML tĩnh duy nhất (`stats.html`), không build, không framework.

## Cập nhật số liệu

Chạy 2 script trong `scripts/`, hoặc đơn giản nhờ Claude — có sẵn skill `cap-nhat-so-lieu` (`.claude/skills/cap-nhat-so-lieu/SKILL.md`) làm hộ toàn bộ quy trình.

## Data model

Toàn bộ số liệu nằm trong object JS ở đầu `stats.html`:

| Key | Nội dung |
|---|---|
| `M` | Danh sách trận |
| `PM` | Điểm danh + bàn thắng theo từng tuần |
| `MG` | Chi tiết bàn thắng / bàn thua |
| `P` | Danh sách cầu thủ — chỉ giữ `n/p/no/t` (tên, vị trí, số áo, loại chính/dự bị) |

Mọi thứ khác — bảng `T` (tổng hợp) và 11 chỉ số mỗi cầu thủ — đều **tính động lúc chạy** từ `M`/`PM`/`MG`/`P`. Tuyệt đối không hardcode số liệu tính toán vào HTML.

## `scripts/`

| File | Việc gì |
|---|---|
| `rebuild_data.py` | Đọc file Google Sheet (.xlsx), dựng lại `M`, `PM`, `P`, `MG` trong `stats.html` |
| `check_stats.py` | Kiểm tra tính nhất quán của số liệu sau khi rebuild, exit khác 0 nếu có lỗi |

## Nguồn dữ liệu

Google Sheet: https://docs.google.com/spreadsheets/d/1Ai6iYdSR4uXXduFNLvKvl9mwh9Sm2ZQZy0DaKyqPG68

## Deploy

Deploy từ nhánh `main` lên Vercel, project `s7cn`.

- Trang live: https://s7cn.vercel.app/stats.html
