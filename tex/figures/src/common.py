"""Thiết lập chung cho các hình vẽ bằng Python của báo cáo.

Mọi script trong thư mục này được chạy từ thư mục gốc của dự án:

    python figures/src/fig_windowing.py
    python figures/src/fig_transfer_time.py
    python figures/src/fig_storage_growth.py

Mỗi script ghi một tệp PNG vào thư mục figures/.
Yêu cầu: Python >= 3.9, numpy, matplotlib (pip install numpy matplotlib).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Thư mục đầu ra: <gốc dự án>/figures
OUT_DIR = Path(__file__).resolve().parent.parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Bảng màu phân loại (3 màu đầu của bảng màu tham chiếu, đã kiểm tra an toàn
# với người mù màu khi dùng tối đa 3 chuỗi dữ liệu).
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
INK = "#0b0b0b"      # chữ chính
INK_2 = "#52514e"    # chữ phụ, trục
GRID = "#d9d8d4"     # lưới
BAND = "#eeede9"     # vùng tô nền nhạt

plt.rcParams.update({
    "font.family": "DejaVu Sans",   # hỗ trợ đầy đủ dấu tiếng Việt
    "font.size": 10,
    "axes.edgecolor": INK_2,
    "axes.labelcolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": INK_2,
    "ytick.color": INK_2,
    "lines.linewidth": 2.0,
    "legend.frameon": False,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


def save(fig, name: str) -> Path:
    path = OUT_DIR / name
    fig.savefig(path, facecolor="white")
    print(f"Đã ghi {path}")
    return path
