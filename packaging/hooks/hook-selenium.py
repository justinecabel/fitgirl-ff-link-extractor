"""The Linux package only needs Selenium Manager for its own architecture."""
import platform

from PyInstaller.utils.hooks import collect_data_files

other_linux = "linux-arm64" if platform.machine().lower() in ("x86_64", "amd64") else "linux-x86_64"
datas = collect_data_files("selenium", excludes=[
    "webdriver/common/macos/**", "webdriver/common/windows/**",
    f"webdriver/common/{other_linux}/**",
])
