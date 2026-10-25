"""Hình: hàm ánh xạ cửa sổ hiển thị CT (Mục Cơ sở lâm sàng).

Vẽ y = clip((x - (L - W/2)) / W, 0, 1) cho ba cửa sổ dùng khi đọc CT sọ não
tìm xuất huyết, và cho thấy độ chênh cường độ hiển thị giữa máu cấp và nhu mô
não dưới mỗi cửa sổ.

Giá trị HU dùng trong hình lấy đúng theo nội dung báo cáo:
  - nhu mô não bình thường: 20--40 HU
  - xuất huyết cấp:          50--70 HU
  - cửa sổ nhu mô não  L=40,  W=80
  - cửa sổ dưới màng cứng L=80, W=200 (nằm trong khoảng L=75--100, W=200--300)
  - cửa sổ xương       L=600, W=2800

Chạy:  python figures/src/fig_windowing.py  ->  figures/fig_windowing.png
"""
import numpy as np
import matplotlib.pyplot as plt

from common import AQUA, BAND, BLUE, INK, INK_2, ORANGE, save

WINDOWS = [
    ("Nhu mô não (L=40, W=80)", 40, 80, BLUE),
    ("Dưới màng cứng (L=80, W=200)", 80, 200, ORANGE),
    ("Xương (L=600, W=2800)", 600, 2800, AQUA),
]
PARENCHYMA = (20, 40)
BLOOD = (50, 70)


def window(x, level, width):
    return np.clip((x - (level - width / 2)) / width, 0.0, 1.0)


def contrast(level, width):
    """Chênh lệch cường độ hiển thị giữa tâm vùng máu cấp và tâm vùng nhu mô."""
    xb, xp = np.mean(BLOOD), np.mean(PARENCHYMA)
    return float(window(xb, level, width) - window(xp, level, width))


def main():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8),
                                   gridspec_kw={"width_ratios": [1.15, 1]})

    # (a) Toàn dải HU
    x = np.linspace(-1100, 2100, 3000)
    for name, L, W, c in WINDOWS:
        ax1.plot(x, window(x, L, W), color=c, label=name)
    ax1.set_xlim(-1100, 2100)
    ax1.set_ylim(-0.03, 1.03)
    ax1.set_xlabel("Giá trị suy giảm (HU)")
    ax1.set_ylabel("Cường độ hiển thị (0 = đen, 1 = trắng)")
    ax1.set_title("(a) Ba cửa sổ trên toàn dải HU", loc="left")
    ax1.annotate("không khí\n≈ −1000 HU", xy=(-1000, 0), xytext=(-1050, 0.35),
                 fontsize=8, color=INK_2,
                 arrowprops=dict(arrowstyle="-", color=INK_2, lw=0.8))
    ax1.legend(loc="lower right", fontsize=8.5)

    # (b) Phóng to vùng mô mềm
    x = np.linspace(-50, 200, 1000)
    ax2.axvspan(*PARENCHYMA, color=BAND, zorder=0)
    ax2.axvspan(*BLOOD, color="#f7dcd0", zorder=0)
    ax2.text(PARENCHYMA[1], 1.05, "nhu mô 20–40 HU ", ha="right",
             va="bottom", fontsize=8, color=INK_2)
    ax2.text(BLOOD[0], 1.05, " máu cấp 50–70 HU", ha="left",
             va="bottom", fontsize=8, color=INK_2)
    for name, L, W, c in WINDOWS:
        d = contrast(L, W)
        ax2.plot(x, window(x, L, W), color=c,
                 label=f"{name.split(' (')[0]}: Δ = {d:.3f}")
    ax2.legend(loc="lower right", fontsize=8.5)
    ax2.set_xlim(-50, 200)
    ax2.set_ylim(-0.03, 1.03)
    ax2.set_xlabel("Giá trị suy giảm (HU)")
    ax2.set_title("(b) Vùng mô mềm; Δ = chênh cường độ máu – nhu mô",
                  loc="left", pad=18)

    fig.tight_layout()
    save(fig, "fig_windowing.png")

    for name, L, W, _ in WINDOWS:
        print(f"{name:32s} Δ(máu - nhu mô) = {contrast(L, W):.3f}")


if __name__ == "__main__":
    main()
