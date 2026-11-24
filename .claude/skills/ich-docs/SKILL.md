---
name: ich-docs
description: Luật làm việc trong repo ich-architecture, nơi team ghi tài liệu, kiến trúc, ý tưởng và quyết định của đồ án hệ thống AI phát hiện xuất huyết não (ICH). Repo gồm các trang web kiến trúc (index, simplified, scenario2, decisions, slicer, dcm4chee), sơ đồ SVG, sơ đồ tuần tự, và báo cáo LaTeX trong tex/. Phần hiện thực (code, cấu hình triển khai, PoC chạy được) nằm ở repo project riêng. Dùng skill này trước khi thêm hay sửa BẤT KỲ thứ gì trong repo, kể cả khi user chỉ nói "cập nhật architecture", "sửa diagram", "thêm ý tưởng", "đề xuất dùng X", "thêm quyết định", "ghi kết quả PoC", "viết vào báo cáo", "thêm trang", "update doc", hoặc muốn thêm code, script, Dockerfile, PoC vào repo này. Skill giúp đưa ý tưởng mới vào đúng chỗ, giữ tài liệu ngắn và viết như người thật viết, và giữ các trang, sơ đồ, báo cáo khớp nhau.
---

# ich-docs: repo tài liệu của đồ án ICH

## Repo này để làm gì

`ich-architecture` là nơi team **thiết kế** đồ án: tài liệu, kiến trúc, ý tưởng, đề xuất, các quyết định và kết quả rút ra từ PoC. Nội dung nằm trong trang web tĩnh (GitHub Pages, có `.nojekyll`) và báo cáo LaTeX. Team sẽ tiếp tục cập nhật repo này khi kiến trúc thay đổi hoặc có ý tưởng mới. Người đọc là giảng viên hướng dẫn, reviewer và chính team.

Phần **hiện thực** (code, cấu hình triển khai, PoC chạy được) thuộc về repo project **[LoveTechwCat/ich-triage](https://github.com/LoveTechwCat/ich-triage)** (xem mục "Code ở đâu" bên dưới). Hai repo chia việc như sau: ở đây ghi *làm gì và vì sao*, còn repo project chứa *code làm việc đó*.

Tài liệu hiện đã dài và có giọng "AI viết". Vì vậy cứ thêm nội dung mới khi cần, nhưng mỗi lần sửa phải làm tài liệu **đúng hơn và gọn hơn**, không phình thêm những chỗ lặp.

## Code ở đâu

- **Không thêm code mới vào repo này.** Script, Dockerfile, plugin, service, notebook hay PoC mới đều thuộc repo project. Riêng JS và CSS của chính trang tài liệu (`assets/`) vẫn sửa ở đây. Nếu user nhờ viết code trong repo này, nói rõ code nên nằm ở repo project và hỏi họ muốn tạo repo đó hay đặt tạm ở đâu, rồi mới làm. Trong tài liệu chỉ ghi link tới code, kèm một câu nói nó làm gì.
- **Code cũ giữ nguyên:** `deploy/staging/` ở yên chỗ cũ cho tới khi team chuyển sang repo project. Sửa lỗi nhỏ trong đó được, nếu user yêu cầu rõ ràng. Không thêm tính năng mới, không thêm thư mục code mới.
- **Đoạn code minh hoạ trong tài liệu:** được dùng khi giúp người đọc hiểu một giao diện. Giữ ngắn (khoảng 15 dòng trở xuống) và ghi rõ "Sketch, not run" (trang web) hoặc "Phác thảo, chưa chạy" (báo cáo).
- Repo project: <https://github.com/LoveTechwCat/ich-triage>, viết hoàn toàn bằng tiếng Anh. Mỗi thành phần có một thư mục (`services/gateway`, `services/ai-worker`, `services/monai-app`, `services/triage-api`, `services/slicer-ich-triage`, `deploy/staging`, `deploy/local`, `tools`), và README của thư mục đó ghi mục đích, giao diện và trạng thái. Khi code cũ trong `deploy/` được chuyển sang đó, xoá ở đây và sửa các link trỏ tới nó.

## Bản đồ repo

| Phần | Nội dung | Ngôn ngữ |
|---|---|---|
| `index.html` | Kịch bản 1: sơ đồ kiến trúc SVG (`#arch`), sơ đồ tuần tự, các tầng, bảng thành phần, Flow 1–5, mục khối AI (`#abstract`), nguyên tắc | English |
| `simplified.html`, `scenario2.html` | Kịch bản 1 rút gọn; kịch bản 2 (GPU ở cơ sở 2) | English |
| `decisions.html` | Bảng quyết định D1–D11, mỗi quyết định một mục `#dN`, câu hỏi reviewer, follow-ups, nguồn | English |
| `slicer.html` | "Slicer + MONAI": phần A trình xem (D10), phần B khối AI (D11) | English |
| `dcm4chee.html` | Tìm hiểu sâu dcm4chee. Ghi lại thứ đã làm, không phải kiến trúc hiện tại | English |
| `assets/site.css`, `site.js` | CSS và JS dùng chung (thanh trên, mục lục, zoom sơ đồ, theme) | |
| `assets/sequence.js` | Bộ vẽ sơ đồ tuần tự (tab, giai đoạn theo `sep`, đi từng bước) | |
| `assets/sequences-s1.js`, `-s2.js` | Dữ liệu sơ đồ tuần tự của từng kịch bản | English |
| `tex/` | Báo cáo: `main.tex`, `contents/*.tex`, hình `figures/arch/*.tex` (TikZ), `refs.bib`, `changelog.txt` | Tiếng Việt |
| `deploy/` | Code cũ (xem mục "Code ở đâu") | |

Kiến trúc hiện tại, để mọi chỗ mô tả giống nhau:
- **Lâm sàng:** máy CT → PACS dcm4chee → 3D Slicer + module ICH Triage (D10, đề xuất).
- **Suy luận AI:** PACS đẩy series một lần sang cổng Orthanc. Khối AI inference = **AI worker** (code của đề tài: job, chuyển NIfTI, dựng SEG/SR, cờ ưu tiên; trong staging chạy dưới dạng plugin `ai_bridge.py` trong Orthanc) + **một máy chủ MONAI Label giữ hai mô hình** (D11): `hemorrhage_approved` chạy cho mọi ca và không bao giờ huấn luyện lại tại chỗ; `hemorrhage_dev` phục vụ gán nhãn và huấn luyện. Máy chủ nằm ở VLAN 30, VLAN 40 chỉ tới được phần `hemorrhage_dev` qua proxy. Khi triển khai thật thì tách thành hai máy chủ.
- **Nghiên cứu:** 3D Slicer (extension MONAILabel) gọi `hemorrhage_dev`, đọc CT và kết quả AI đã khử định danh qua DICOMweb của Orthanc. CT và mọi mask của nó được đổi UID theo cùng một quy tắc băm có khoá. Kết quả AI làm bản nháp (chỉ cho ca huấn luyện). Mỗi lần lưu là một phiên bản nhãn mới, ghi ai sửa và khi nào; người duyệt chọn một phiên bản. Bản sửa của bác sĩ đi PACS → Orthanc → kho nhãn, ở trạng thái chưa duyệt. Registry lưu MONAI bundle; chỉ bundle đã duyệt mới thành `hemorrhage_approved`.
- **Dữ liệu:** SeaweedFS, PostgreSQL, OpenLDAP, sao lưu bằng pgBackRest/rclone lên cloud.

## Đưa ý tưởng hoặc thay đổi kiến trúc vào repo

Một ý tưởng thường đi qua ba bước. Ghi nó ở đúng chỗ của bước đó:

1. **Mới là ý tưởng hoặc đề xuất** (ví dụ "dùng 3D Slicer + MONAI"): thêm hoặc cập nhật một quyết định `Dn` trong `decisions.html`, trạng thái "proposed" (dùng class `dn open`), có bảng phương án, lý do và cái giá phải trả. Nếu cần đánh giá dài (so với yêu cầu, rủi ro, kế hoạch PoC), viết thành một trang riêng như `slicer.html` và link từ `Dn`. Trước khi tạo trang mới, hỏi user xem có muốn gộp vào trang đã có không.
2. **Đang thử bằng PoC:** code PoC nằm ở repo project. Ở đây chỉ ghi mục tiêu, tiêu chí đạt và kết quả (bảng đạt/không đạt, ảnh chụp), kèm link tới commit hoặc PR bên repo project.
3. **Đã chốt:** cập nhật kiến trúc ở mọi nơi theo danh sách "Giữ các nơi khớp nhau" bên dưới, đổi trạng thái `Dn`, và bỏ các câu "chưa chốt" hay "TBD" còn sót.

Khi user đưa tài liệu hay sơ đồ từ bên ngoài (ví dụ sơ đồ tương tác Slicer ↔ MONAI Label), trước hết xác định nó thuộc luồng nào của kiến trúc. Sau đó ghi điểm khớp và điểm lệch với thiết kế hiện tại, thay vì chép lại nguyên văn.

## Viết ngắn, viết như người

Người đọc lướt để tìm một câu trả lời. Văn dài và rập khuôn làm họ bỏ qua cả phần quan trọng. Khi viết hoặc sửa:

- **Sửa chỗ đã có trước khi thêm mới.** Nếu ý đã có ở một trang hay một mục, sửa ở đó. Không thêm callout, mục hay trang mới chỉ để nói lại điều đã nói. Nội dung mới thật sự (ý tưởng, quyết định, kết quả PoC) thì cứ thêm, theo mục "Đưa ý tưởng hoặc thay đổi kiến trúc vào repo".
- **Câu trả lời đi trước.** Câu đầu của mỗi mục trả lời thẳng câu hỏi của mục đó. Bỏ câu dẫn ("Trong phần này chúng ta sẽ…", "This section describes…") và đoạn tóm tắt lặp lại ở cuối.
- **Một quyết định (Dn)** gồm: bối cảnh, lựa chọn, vì sao, cái giá phải trả, và khi nào thì xem lại. Vài đoạn ngắn cộng một bảng phương án là đủ.
- **Bảng** chỉ dùng khi so ít nhất hai phương án theo ít nhất hai tiêu chí. Danh sách chỉ dùng khi các ý thật sự song song. Còn lại viết thành câu.
- **Bỏ dấu hiệu văn AI:**
  - Tiếng Anh: "Notably", "It's worth noting", "seamless", "robust", "leverage", "delve", câu kết kiểu "In summary…".
  - Tiếng Việt: "Đáng chú ý là", "Nhìn chung", "Có thể thấy rằng", "Tóm lại" lặp đi lặp lại.
  - Không dùng em dash, không in đậm khắp nơi, không xếp callout chồng callout, không dùng emoji, không nhồi ba tính từ một lúc.
- **Ghi rõ mức kiểm chứng.** Phân biệt thứ đã chạy trong PoC với thứ chỉ đọc từ tài liệu ("per the docs", "chưa chạy thử"). Không viết như thể đã kiểm chứng khi chưa.
- **Độ dài:** khi sửa một mục, độ dài không nên tăng, trừ khi thêm nội dung mới thật sự. Nếu thấy đoạn cũ thừa, cắt đi trong cùng lần sửa và báo cho user.

## Giữ các nơi khớp nhau

Một thành phần thường xuất hiện ở 6–8 chỗ. Khi đổi tên sản phẩm, luồng hay vai trò của một khối, kiểm tra lần lượt:

1. Chữ trong SVG của `index.html` và `simplified.html`, `scenario2.html`, gồm khối, nhãn mũi tên, `<desc>`, chú thích hình và `data-desc` của các nút highlight.
2. Bảng thành phần (glossary), thẻ các tầng, các bước Flow, mục `#abstract` trong `index.html`.
3. `decisions.html`: dòng trong bảng index và mục `#dN`.
4. `assets/sequences-s*.js`: tên và `sub` của participant, các bước liên quan.
5. `slicer.html`, nếu thay đổi chạm tới trình xem hoặc khối AI.
6. Báo cáo: `tex/contents/architecture.tex` (thành phần, bảng kết nối, các luồng, hợp đồng AI), `solutions.tex`, `figures/arch/*.tex`. Ghi một dòng vào `tex/changelog.txt`.

Dùng grep tìm tên cũ trên toàn repo trước khi báo xong. Ví dụ: `grep -rn -i "ohif\|tbd\|to be decided" --include=*.html --include=*.js --include=*.tex .`. Những chỗ nói về phương án đã so sánh hoặc PoC đã làm (như OHIF trong D10) thì giữ nguyên.

## Ghi chú kỹ thuật

- **Trang mới:** chép phần `<head>` và thanh `nav.scen` từ một trang có sẵn, rồi thêm link trang mới vào `nav.scen` của **mọi** trang. Thanh trên phải nằm một hàng; kiểm tra ở độ rộng 1280, 900 và 375 px.
- **Sơ đồ tuần tự:** chia giai đoạn bằng `{t: "sep"}` ở cấp ngoài cùng, không đặt bên trong `alt/par/loop`. Mỗi giai đoạn nên khoảng 15 bước trở xuống. Mọi `from/to` phải là id có trong `participants`; kiểm tra bằng `node --check` và mở trang xem.
- **Chữ trong SVG:** sau khi đổi chữ, mở trang và kiểm tra chữ không tràn khối và không đè nhau (dùng `getBBox()` trong trình duyệt).
- **Xem thử:** `python -m http.server 8765` ở thư mục gốc, rồi mở `http://127.0.0.1:8765/`. Trình duyệt hay giữ bản cũ của `assets/*.js|css`; tải lại có bỏ cache.
- **LaTeX:** sửa file `.tex` bằng script Python đặt trong file (viết bằng công cụ Write), không viết inline trong lệnh shell. Lệnh shell có thể nuốt `\\`, làm hỏng `\textbf`, `\\` cuối dòng bảng hay xuống dòng trong node TikZ. Sau khi sửa, kiểm tra số `{` và `}` cân bằng và các dòng bảng kết thúc bằng `\\`. MiKTeX trên máy dev hiện lỗi font `vntex` ngay cả với `main`; nếu không build được thì nói rõ, đừng báo là đã build.
- **Xuống dòng:** repo lưu LF, working copy có thể là CRLF (`core.autocrlf`). Khi sửa bằng script, đọc và ghi với `newline=""` và giữ đúng kiểu xuống dòng của file.

## Commit và PR

- Theo Conventional Commits như lịch sử repo: `docs:` cho nội dung, `feat:` cho tính năng trang (JS), `style:` cho CSS, `fix:` cho lỗi. Thân commit nói thay đổi gì và vì sao, bằng tiếng Anh.
- Mỗi việc một nhánh có tên rõ nghĩa, ví dụ `docs/slicer-monai-architecture`. Không commit thẳng vào `main`.
- Mô tả PR liệt kê phần đã làm và phần **chưa kiểm chứng**.
