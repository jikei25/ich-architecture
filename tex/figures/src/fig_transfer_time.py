"""Hình: thời gian truyền một ca CT sọ não theo băng thông đường truyền.

Mô hình đơn giản:  t = S * 8 / (B * eta)
  S   : dung lượng ca chụp (MB). Báo cáo dùng khoảng 100--500 MB/ca.
  B   : băng thông danh định (Mbit/s).
  eta : hiệu suất sử dụng đường truyền thực tế (giả định 0,7 do overhead
        TCP/TLS, chia sẻ đường truyền với các dịch vụ khác của bệnh viện).
  R   : tỉ lệ nén không mất mát (giả định 2,5:1, là tham số, có thể đổi).

Đây là ước lượng bậc độ lớn để minh hoạ lập luận "ghi cục bộ trước", không
phải kết quả đo. Mọi tham số được khai báo ở đầu tệp.

Chạy:  python figures/src/fig_transfer_time.py  ->  figures/fig_transfer_time.png
"""
import numpy as np
import matplotlib.pyplot as plt

from common import BLUE, INK, INK_2, ORANGE, save

SIZES_MB = [(250, BLUE), (500, ORANGE)]
ETA = 0.7
LOSSLESS_RATIO = 2.5
REFERENCE_LINKS = [  # (nhãn, Mbit/s)
    ("4G/ADSL\nyếu", 5),
    ("cáp quang\nphổ thông", 50),
    ("LAN\n1 Gbps", 1000),
]


def minutes(size_mb, bw_mbps, ratio=1.0):
    return size_mb / ratio * 8.0 / (bw_mbps * ETA) / 60.0


def main():
    bw = np.logspace(0, 3, 400)  # 1 .. 1000 Mbit/s
    fig, ax = plt.subplots(figsize=(8.2, 4.4))

    for s, c in SIZES_MB:
        ax.plot(bw, minutes(s, bw), color=c, label=f"{s} MB, không nén")
        ax.plot(bw, minutes(s, bw, LOSSLESS_RATIO), color=c, ls="--",
                label=f"{s} MB, nén không mất mát {LOSSLESS_RATIO}:1")

    for y, txt in [(1, "1 phút"), (10, "10 phút"), (60, "1 giờ")]:
        ax.axhline(y, color=INK_2, lw=0.8, ls=":")
        ax.text(980, y * 1.1, txt, ha="right", fontsize=8, color=INK_2)

    for name, b in REFERENCE_LINKS:
        ax.axvline(b, color=INK_2, lw=0.8, ls="-", alpha=0.5)
        ax.text(b, 250, name, ha="center", va="top", fontsize=8, color=INK)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 1000)
    ax.set_ylim(0.01, 300)
    ax.set_xlabel("Băng thông danh định (Mbit/s, thang log)")
    ax.set_ylabel("Thời gian truyền một ca (phút, thang log)")
    ax.set_title(f"Thời gian truyền một ca CT sọ não (hiệu suất đường truyền {ETA:.0%})",
                 loc="left")
    ax.legend(loc="lower left", fontsize=8.5)
    fig.tight_layout()
    save(fig, "fig_transfer_time.png")

    print("Bảng tra (phút):")
    for name, b in REFERENCE_LINKS:
        row = ", ".join(
            f"{s}MB={minutes(s, b):.2f}/{minutes(s, b, LOSSLESS_RATIO):.2f}"
            for s, _ in SIZES_MB)
        print(f"  {name.replace(chr(10), ' '):22s} {b:5d} Mbps: {row}")


if __name__ == "__main__":
    main()
