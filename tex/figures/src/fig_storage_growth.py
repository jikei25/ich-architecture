"""Hình: ước lượng dung lượng lưu trữ tích luỹ và phân tầng theo vòng đời.

Giả định (khai báo tường minh, có thể thay đổi):
  - Số ca CT sọ não mỗi ngày theo mẫu bối cảnh (Bảng các mẫu bối cảnh):
      A: 60 ca/ngày (>50), B: 30 ca/ngày (10--50), C: 5 ca/ngày (<10).
  - Dung lượng gốc 250 MB/ca (giữa khoảng 100--500 MB nêu trong báo cáo).
  - Lưu trữ ở dạng nén không mất mát tỉ lệ 2,5:1  ->  100 MB/ca trên đĩa.
  - Phân tầng theo tuổi dữ liệu, dựa trên quan sát tần suất truy cập ảnh
    giảm mạnh sau 6--12 tháng và hiếm khi truy cập sau 2--3 năm:
      nóng  : ca chụp <= 1 năm tuổi
      ấm    : 1--3 năm tuổi
      lạnh  : > 3 năm tuổi
  - Chỉ tính CT sọ não; toàn bộ khoa chẩn đoán hình ảnh sẽ lớn hơn nhiều.

Chạy:  python figures/src/fig_storage_growth.py  ->  figures/fig_storage_growth.png
"""
import numpy as np
import matplotlib.pyplot as plt

from common import AQUA, BLUE, INK, INK_2, ORANGE, save

STUDIES_PER_DAY = {"A: Trung ương": (60, BLUE),
                   "B: Tuyến tỉnh": (30, ORANGE),
                   "C: Tuyến huyện": (5, AQUA)}
RAW_MB = 250
LOSSLESS_RATIO = 2.5
YEARS = 10
HOT_MAX_Y, WARM_MAX_Y = 1.0, 3.0
TIER_COLORS = ["#0d366b", "#2a78d6", "#a9c9f0"]  # một sắc độ xanh: đậm = nóng


def tb_per_year(per_day):
    return per_day * 365 * RAW_MB / LOSSLESS_RATIO / 1e6  # MB -> TB


def tiers(t, per_day):
    """Dung lượng (TB) trong mỗi tầng tại thời điểm t năm sau khi vận hành."""
    r = tb_per_year(per_day)
    hot = r * np.minimum(t, HOT_MAX_Y)
    warm = r * np.clip(t - HOT_MAX_Y, 0, WARM_MAX_Y - HOT_MAX_Y)
    cold = r * np.maximum(t - WARM_MAX_Y, 0)
    return hot, warm, cold


def main():
    t = np.linspace(0, YEARS, 401)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.9))

    # (a) Dung lượng tích luỹ theo bối cảnh
    for name, (n, c) in STUDIES_PER_DAY.items():
        total = tb_per_year(n) * t
        ax1.plot(t, total, color=c)
        ax1.text(YEARS + 0.15, total[-1], f"{name}\n{total[-1]:.1f} TB",
                 va="center", fontsize=8, color=INK)
    ax1.set_xlim(0, YEARS)
    ax1.set_ylim(0, None)
    ax1.set_xlabel("Số năm vận hành")
    ax1.set_ylabel("Dung lượng tích luỹ (TB)")
    ax1.set_title("(a) Tích luỹ theo mẫu bối cảnh", loc="left")

    # (b) Phân tầng cho bối cảnh B
    nB, _ = STUDIES_PER_DAY["B: Tuyến tỉnh"]
    hot, warm, cold = tiers(t, nB)
    ax2.stackplot(t, hot, warm, cold, colors=TIER_COLORS,
                  edgecolor="white", linewidth=0.8)
    labels = ["nóng (≤ 1 năm)", "ấm (1–3 năm)", "lạnh (> 3 năm)"]
    ys = [hot[-1] / 2, hot[-1] + warm[-1] / 2,
          hot[-1] + warm[-1] + cold[-1] / 2]
    for lab, y, v in zip(labels, ys, [hot[-1], warm[-1], cold[-1]]):
        ax2.text(YEARS + 0.15, y, f"{lab}: {v:.1f} TB", va="center",
                 fontsize=8, color=INK)
    ax2.set_xlim(0, YEARS)
    ax2.set_ylim(0, None)
    ax2.set_xlabel("Số năm vận hành")
    ax2.set_ylabel("Dung lượng (TB)")
    ax2.set_title("(b) Bối cảnh B, phân theo tầng lưu trữ", loc="left")

    fig.tight_layout()
    save(fig, "fig_storage_growth.png")

    for name, (n, _) in STUDIES_PER_DAY.items():
        r = tb_per_year(n)
        print(f"{name:16s}: {r:.2f} TB/năm, sau {YEARS} năm {r*YEARS:.1f} TB; "
              f"tầng nóng ổn định ở {r*HOT_MAX_Y:.2f} TB")


if __name__ == "__main__":
    main()
