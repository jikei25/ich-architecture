# Mã nguồn các hình vẽ bằng Python

Các hình PNG trong thư mục `figures/` được sinh bởi các script ở đây.
Chạy từ thư mục gốc của dự án (cần Python >= 3.9, `numpy`, `matplotlib`):

```
pip install numpy matplotlib
python figures/src/fig_windowing.py       # -> figures/fig_windowing.png
python figures/src/fig_transfer_time.py   # -> figures/fig_transfer_time.png
python figures/src/fig_storage_growth.py  # -> figures/fig_storage_growth.png
```

| Script | Hình trong báo cáo | Nội dung |
|---|---|---|
| `fig_windowing.py` | `fig:windowing` (Mục Cơ sở lâm sàng) | Hàm ánh xạ cửa sổ CT, độ chênh máu–nhu mô theo cửa sổ |
| `fig_transfer_time.py` | `fig:transfer` (Mục Kiến trúc) | Thời gian truyền một ca CT theo băng thông |
| `fig_storage_growth.py` | `fig:storage` (Mục Kiến trúc) | Dung lượng tích luỹ và phân tầng lưu trữ |

`common.py` chứa bảng màu, phông chữ (DejaVu Sans, hỗ trợ tiếng Việt) và hàm lưu.
Mọi giả định định lượng (số ca/ngày, dung lượng/ca, tỉ lệ nén, hiệu suất đường
truyền, ngưỡng phân tầng) được khai báo dưới dạng hằng số ở đầu mỗi script; đây là
ước lượng minh hoạ, không phải số liệu đo.

Cập nhật: 24/09/2026 (Vinh).
