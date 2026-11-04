"""In-app user guide (Vietnamese). Rendered by the Guide tab in app.py.
Keep this in sync with docs/GUIDE.md.
"""

GUIDE_SECTIONS: list[tuple[str, str]] = [
    ("1. Bắt đầu trong 2 phút", """\
1) Cắm điện thoại bằng USB (bật USB debugging) hoặc mở giả lập LDPlayer / Android Emulator.
2) Bấm Refresh (phím F5) ở cột trái, chọn thiết bị trong danh sách.
3) Màn hình điện thoại hiện ở khung LIVE SCREEN: click = tap, kéo = swipe, click chuột phải = nhấn giữ.
4) Nếu chưa thấy thiết bị: kiểm tra cáp, chấp nhận hộp thoại "Allow USB debugging" trên điện thoại,
   hoặc với LDPlayer hãy chắc chắn giả lập đã boot xong."""),
    ("2. Tab Control - điều khiển tay", """\
- Hàng phím điều hướng: Home, Back, App Switch (đa nhiệm), Power, Wakeup, Menu, Enter, Escape.
- Volume / media / D-pad cho TV box và giả lập.
- Tap / Swipe theo tọa độ: khi cần bấm chính xác một điểm đã biết tọa độ (lấy tọa độ ở tab Inspector).
- Type text: gõ nội dung vào ô đang focus trên điện thoại (hỗ trợ tiếng Anh tốt nhất; tiếng Việt có dấu
  hãy gõ trực tiếp trên điện thoại).
- Quick actions: Wake + unlock swipe, mở URL/activity theo component, Reboot, xem pin."""),
    ("3. Tab Apps - quản lý ứng dụng", """\
- List apps: liệt kê app (chỉ app bên thứ ba hoặc tất cả), lọc theo tên package.
- Launch / Force stop / Clear data / Uninstall cho app đang chọn.
- Current focus: xem app/activity nào đang ở foreground - rất hữu ích khi viết assert_package.
- Install APK...: cài file .apk từ máy tính (tùy chọn -r ghi đè, -g cấp sẵn quyền)."""),
    ("4. Tab Inspector - soi UI như Appium Inspector", """\
- Dump UI now: chụp cây giao diện hiện tại của app (uiautomator).
- Click một element để xem text, resource-id, content-desc, bounds và locator gợi ý.
- Tap selected element: bấm thử element đó trên máy thật.
- Add assert_text step: biến element thành một bước kiểm chứng trong scenario đang record.
Locator ưu tiên: id (ổn định nhất) > accessibility id (content-desc) > xpath theo text."""),
    ("5. Tab Logcat - lấy log chuyên nghiệp", """\
- Start/Stop: stream log trực tiếp, tô màu theo mức E (đỏ) / W (vàng) / F / I.
- Filter: lọc theo từ khóa, tên package hoặc tag; Level: chỉ xem từ mức đã chọn trở lên.
- Save log...: lưu toàn bộ log đang xem ra file .log (mặc định trong output/logs).
- Crash snapshot: trích ngay đoạn FATAL EXCEPTION / AndroidRuntime gần nhất - gửi kèm bug report là chuẩn QA.
- Clear buffer trước khi tái hiện bug để log sạch, dễ đọc."""),
    ("6. Tab Record & Automation - ghi và phát lại", """\
- Start recording (F9): từ lúc này MỌI thao tác của bạn (tap trên mirror, phím, gõ chữ, mở app)
  đều thành từng Step trong scenario.
- Thêm bước tay: wait (chờ), assert_text (màn hình phải có chữ này), assert_package (app phải đang focus),
  assert_no_crash (không có crash trong log), shell (lệnh adb shell), screenshot, key.
- Sửa thứ tự bằng Move up / Move down, xóa bằng Delete selected step.
- Save/Load scenario JSON: lưu kịch bản thành file, dùng lại hoặc chia sẻ cho đồng đội.
- Replay scenario: phát lại toàn bộ kịch bản trên thiết bị hiện tại."""),
    ("7. Tự sinh code (Auto-generate code)", """\
Từ một scenario đã ghi, xuất ra source code để đưa vào project automation thật:
- python_adb: Python thuần dùng subprocess + adb, KHÔNG cần cài thêm gì - chạy ngay.
- appium: script Appium Python (UiAutomator2) cho team đang dùng Appium server.
- pytest: module pytest hoàn chỉnh, một test cho một scenario - đưa vào CI được ngay.
- shell: script bash chứa các lệnh adb tương ứng.
Bấm Preview để xem trước, Generate + save... để lưu file."""),
    ("8. Tab Screen Record + Files + Shell", """\
- Screen Record: quay màn hình máy thành MP4 (tối đa 180 giây/clip theo giới hạn Android),
  Stop sẽ tự kéo file về output/videos - đính kèm bug report rất tiện.
- Files: duyệt /sdcard, Push file từ máy tính lên, Pull file về máy tính.
- Shell: gõ lệnh adb shell trực tiếp và xem kết quả (Enter để chạy)."""),
    ("9. Tab Test Run & Report - chạy kiểm thử + báo cáo", """\
- Run scenario + build HTML report: chạy scenario như một bài test thật.
  Mỗi bước có screenshot riêng, assert nào fail sẽ ghi rõ lý do, kèm trích đoạn logcat cuối báo cáo.
- Báo cáo là MỘT file HTML duy nhất (ảnh nhúng sẵn) trong output/reports - gửi cho ai cũng mở xem được,
  không cần cài gì thêm. Đây là cách bàn giao kết quả automation chuyên nghiệp nhất trong tool này.
- Tích "Stop on first failure" khi debug để dừng ngay ở bước lỗi đầu tiên."""),
    ("10. Phím tắt", """\
F5    Làm mới danh sách thiết bị
F6    Làm mới màn hình mirror
F9    Bật / tắt ghi scenario (Record)
Trong khung mirror: Click = Tap - Kéo thả = Swipe - Click phải = Nhấn giữ (long press)"""),
    ("11. Xử lý sự cố thường gặp", """\
- Không thấy thiết bị: gõ "adb devices" ở tab Shell ngoài (hoặc terminal) - trạng thái "unauthorized"
  nghĩa là chưa bấm Allow trên điện thoại; "offline" thì rút cáp cắm lại / restart giả lập.
- Báo "adb not found": cài Android platform-tools vào PATH, hoặc đặt biến môi trường ADB_PATH
  trỏ thẳng tới file adb.exe / adb.
- App không mở được bằng Launch: một số bản Android/giả lập thiếu lệnh monkey - tool đã tự fallback
  sang resolve-activity + am start; nếu vẫn lỗi, mở app bằng tay rồi dùng Current focus để lấy package.
- assert_package fail dù app đang mở: chờ app load xong (thêm bước wait 2-3 giây sau launch).
- Mirror không cập nhật: tắt Auto-refresh rồi bật lại, hoặc bấm Refresh screen (F6)."""),
    ("12. Dùng bằng dòng lệnh (CLI) cho CI", """\
python main.py devices
python main.py screenshot out.png
python main.py logcat --seconds 10 --out output/logs/run.log
python main.py run scenarios/example_smoke.json --report output/reports
python main.py gen scenarios/example_smoke.json --target pytest --out test_smoke.py
Mã thoát 0 = pass, 1 = có bước fail - gắn vào Jenkins/GitHub Actions/n8n đều được."""),
]

ABOUT_TEXT = """ADB Control Studio 1.1

Full ADB control studio: live mirror & control, logcat, UI inspector,
automation recorder, code generation (Python-ADB / Appium / pytest / shell),
screen recording and self-contained HTML test reports.

Pure Python (stdlib + Tkinter). No Appium server, no Node required.
Repository: https://github.com/duybongson/adb-control-studio"""
